#include <BRepBndLib.hxx>
#include <BRep_Builder.hxx>
#include <BRepCheck_Analyzer.hxx>
#include <BRepGProp.hxx>
#include <BRepMesh_IncrementalMesh.hxx>
#include <BRep_Tool.hxx>
#include <Bnd_Box.hxx>
#include <GProp_GProps.hxx>
#include <IFSelect_ReturnStatus.hxx>
#include <Poly_Triangle.hxx>
#include <Poly_Triangulation.hxx>
#include <STEPControl_Reader.hxx>
#include <TopExp_Explorer.hxx>
#include <TopLoc_Location.hxx>
#include <TopoDS.hxx>
#include <TopoDS_Face.hxx>
#include <TopoDS_Compound.hxx>
#include <TopoDS_Shape.hxx>
#include <TopoDS_Shell.hxx>
#include <TopoDS_Solid.hxx>
#include <TopAbs_Orientation.hxx>
#include <TopAbs_ShapeEnum.hxx>
#include <gp_Pnt.hxx>
#include <gp_Trsf.hxx>

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {

struct Args {
  std::string input;
  std::string output;
  std::string corpus_id;
  std::string source_group;
  std::string mesh_output;
  double relative_deflection = 1.0e-3;
  double angular_deflection = 0.35;
};

std::string json_escape(const std::string& value) {
  std::ostringstream out;
  for (const unsigned char c : value) {
    switch (c) {
      case '\"': out << "\\\""; break;
      case '\\': out << "\\\\"; break;
      case '\b': out << "\\b"; break;
      case '\f': out << "\\f"; break;
      case '\n': out << "\\n"; break;
      case '\r': out << "\\r"; break;
      case '\t': out << "\\t"; break;
      default:
        if (c < 0x20) {
          out << "\\u" << std::hex << std::setw(4) << std::setfill('0')
              << static_cast<int>(c) << std::dec << std::setfill(' ');
        } else {
          out << c;
        }
    }
  }
  return out.str();
}

void write_number(std::ostream& out, const double value) {
  if (std::isfinite(value)) {
    out << std::setprecision(17) << value;
  } else {
    out << "null";
  }
}

Args parse_args(const int argc, char** argv) {
  Args args;
  for (int i = 1; i < argc; ++i) {
    const std::string key = argv[i];
    auto require_value = [&]() -> std::string {
      if (i + 1 >= argc) {
        throw std::runtime_error("missing value after " + key);
      }
      return argv[++i];
    };
    if (key == "--input") args.input = require_value();
    else if (key == "--output") args.output = require_value();
    else if (key == "--id") args.corpus_id = require_value();
    else if (key == "--group") args.source_group = require_value();
    else if (key == "--mesh-output") args.mesh_output = require_value();
    else if (key == "--relative-deflection") args.relative_deflection = std::stod(require_value());
    else if (key == "--angular-deflection") args.angular_deflection = std::stod(require_value());
    else throw std::runtime_error("unknown argument: " + key);
  }
  if (args.input.empty() || args.output.empty() || args.corpus_id.empty()) {
    throw std::runtime_error("required: --input FILE --output JSON --id ID [--group GROUP]");
  }
  if (!(args.relative_deflection > 0.0) || !(args.angular_deflection > 0.0)) {
    throw std::runtime_error("meshing deflections must be positive");
  }
  return args;
}

int count_subshapes(const TopoDS_Shape& shape, const TopAbs_ShapeEnum type) {
  int count = 0;
  for (TopExp_Explorer it(shape, type); it.More(); it.Next()) ++count;
  return count;
}

struct Vertex {
  double x = 0.0;
  double y = 0.0;
  double z = 0.0;
};

struct Triangle {
  std::array<std::uint32_t, 3> v{};
};

struct QuantizedKey {
  std::int64_t x = 0;
  std::int64_t y = 0;
  std::int64_t z = 0;
  bool operator==(const QuantizedKey& other) const {
    return x == other.x && y == other.y && z == other.z;
  }
};

struct QuantizedKeyHash {
  std::size_t operator()(const QuantizedKey& key) const noexcept {
    std::size_t h = std::hash<std::int64_t>{}(key.x);
    h ^= std::hash<std::int64_t>{}(key.y) + 0x9e3779b97f4a7c15ULL + (h << 6U) + (h >> 2U);
    h ^= std::hash<std::int64_t>{}(key.z) + 0x9e3779b97f4a7c15ULL + (h << 6U) + (h >> 2U);
    return h;
  }
};

struct EdgeKey {
  std::uint32_t a = 0;
  std::uint32_t b = 0;
  EdgeKey(const std::uint32_t u, const std::uint32_t v)
      : a(std::min(u, v)), b(std::max(u, v)) {}
  bool operator<(const EdgeKey& other) const {
    return a < other.a || (a == other.a && b < other.b);
  }
};

struct UnionFind {
  explicit UnionFind(const std::size_t n) : parent(n), rank(n, 0) {
    std::iota(parent.begin(), parent.end(), 0U);
  }
  std::size_t find(std::size_t x) {
    while (parent[x] != x) {
      parent[x] = parent[parent[x]];
      x = parent[x];
    }
    return x;
  }
  void unite(std::size_t a, std::size_t b) {
    a = find(a); b = find(b);
    if (a == b) return;
    if (rank[a] < rank[b]) std::swap(a, b);
    parent[b] = a;
    if (rank[a] == rank[b]) ++rank[a];
  }
  std::vector<std::size_t> parent;
  std::vector<unsigned char> rank;
};

struct MeshStats {
  bool meshing_done = false;
  std::size_t raw_vertices = 0;
  std::size_t welded_vertices = 0;
  std::size_t triangles = 0;
  std::size_t degenerate_triangles = 0;
  std::size_t unique_edges = 0;
  std::size_t boundary_edges = 0;
  std::size_t nonmanifold_edges = 0;
  std::size_t connected_components = 0;
  double surface_area = 0.0;
  double signed_volume = 0.0;
  double weld_tolerance = 0.0;
  std::vector<Vertex> vertices;
  std::vector<Triangle> faces;
};

MeshStats triangulate_and_audit(const TopoDS_Shape& shape,
                                const double bbox_diagonal,
                                const double relative_deflection,
                                const double angular_deflection) {
  MeshStats stats;
  const double absolute_deflection = std::max(bbox_diagonal * relative_deflection, 1.0e-7);
  BRepMesh_IncrementalMesh mesher(shape, absolute_deflection, false, angular_deflection, true);
  stats.meshing_done = mesher.IsDone();
  if (!stats.meshing_done) return stats;

  std::vector<Vertex> raw_vertices;
  std::vector<std::array<std::uint32_t, 3>> raw_triangles;
  for (TopExp_Explorer fit(shape, TopAbs_FACE); fit.More(); fit.Next()) {
    const TopoDS_Face face = TopoDS::Face(fit.Current());
    TopLoc_Location location;
    const Handle(Poly_Triangulation) triangulation = BRep_Tool::Triangulation(face, location);
    if (triangulation.IsNull()) continue;
    const gp_Trsf transform = location.Transformation();
    const std::uint32_t offset = static_cast<std::uint32_t>(raw_vertices.size());
    for (int i = 1; i <= triangulation->NbNodes(); ++i) {
      gp_Pnt p = triangulation->Node(i);
      p.Transform(transform);
      raw_vertices.push_back({p.X(), p.Y(), p.Z()});
    }
    for (int i = 1; i <= triangulation->NbTriangles(); ++i) {
      int a = 0, b = 0, c = 0;
      triangulation->Triangle(i).Get(a, b, c);
      std::array<std::uint32_t, 3> tri{
          offset + static_cast<std::uint32_t>(a - 1),
          offset + static_cast<std::uint32_t>(b - 1),
          offset + static_cast<std::uint32_t>(c - 1)};
      if (face.Orientation() == TopAbs_REVERSED) std::swap(tri[1], tri[2]);
      raw_triangles.push_back(tri);
    }
  }
  stats.raw_vertices = raw_vertices.size();
  stats.triangles = raw_triangles.size();
  stats.weld_tolerance = std::max(bbox_diagonal * 1.0e-9, 1.0e-9);
  if (raw_vertices.empty() || raw_triangles.empty()) return stats;

  std::unordered_map<QuantizedKey, std::uint32_t, QuantizedKeyHash> map;
  std::vector<Vertex> vertices;
  std::vector<std::uint32_t> remap(raw_vertices.size());
  map.reserve(raw_vertices.size());
  vertices.reserve(raw_vertices.size());
  for (std::size_t i = 0; i < raw_vertices.size(); ++i) {
    const Vertex& p = raw_vertices[i];
    const QuantizedKey key{
        static_cast<std::int64_t>(std::llround(p.x / stats.weld_tolerance)),
        static_cast<std::int64_t>(std::llround(p.y / stats.weld_tolerance)),
        static_cast<std::int64_t>(std::llround(p.z / stats.weld_tolerance))};
    const auto found = map.find(key);
    if (found == map.end()) {
      const auto index = static_cast<std::uint32_t>(vertices.size());
      map.emplace(key, index);
      vertices.push_back(p);
      remap[i] = index;
    } else {
      remap[i] = found->second;
    }
  }
  stats.welded_vertices = vertices.size();

  std::vector<Triangle> triangles;
  triangles.reserve(raw_triangles.size());
  const double area_epsilon = std::max(bbox_diagonal * bbox_diagonal * 1.0e-24, 1.0e-30);
  for (const auto& raw : raw_triangles) {
    Triangle tri{{remap[raw[0]], remap[raw[1]], remap[raw[2]]}};
    if (tri.v[0] == tri.v[1] || tri.v[1] == tri.v[2] || tri.v[2] == tri.v[0]) {
      ++stats.degenerate_triangles;
      continue;
    }
    const Vertex& a = vertices[tri.v[0]];
    const Vertex& b = vertices[tri.v[1]];
    const Vertex& c = vertices[tri.v[2]];
    const double abx = b.x - a.x, aby = b.y - a.y, abz = b.z - a.z;
    const double acx = c.x - a.x, acy = c.y - a.y, acz = c.z - a.z;
    const double nx = aby * acz - abz * acy;
    const double ny = abz * acx - abx * acz;
    const double nz = abx * acy - aby * acx;
    const double double_area = std::sqrt(nx * nx + ny * ny + nz * nz);
    if (!(double_area > area_epsilon)) {
      ++stats.degenerate_triangles;
      continue;
    }
    stats.surface_area += 0.5 * double_area;
    stats.signed_volume +=
        (a.x * (b.y * c.z - b.z * c.y) -
         a.y * (b.x * c.z - b.z * c.x) +
         a.z * (b.x * c.y - b.y * c.x)) / 6.0;
    triangles.push_back(tri);
  }
  stats.triangles = triangles.size();

  std::map<EdgeKey, std::size_t> edge_counts;
  UnionFind components(vertices.size());
  std::vector<bool> used(vertices.size(), false);
  for (const Triangle& tri : triangles) {
    for (int i = 0; i < 3; ++i) used[tri.v[i]] = true;
    components.unite(tri.v[0], tri.v[1]);
    components.unite(tri.v[1], tri.v[2]);
    components.unite(tri.v[2], tri.v[0]);
    ++edge_counts[EdgeKey(tri.v[0], tri.v[1])];
    ++edge_counts[EdgeKey(tri.v[1], tri.v[2])];
    ++edge_counts[EdgeKey(tri.v[2], tri.v[0])];
  }
  stats.unique_edges = edge_counts.size();
  for (const auto& [edge, count] : edge_counts) {
    (void)edge;
    if (count == 1) ++stats.boundary_edges;
    else if (count > 2) ++stats.nonmanifold_edges;
  }
  std::map<std::size_t, bool> roots;
  for (std::size_t i = 0; i < vertices.size(); ++i) {
    if (used[i]) roots[components.find(i)] = true;
  }
  stats.connected_components = roots.size();
  stats.vertices = std::move(vertices);
  stats.faces = std::move(triangles);
  return stats;
}

void write_obj(const std::string& path, const MeshStats& mesh) {
  if (path.empty()) return;
  std::ofstream out(path);
  if (!out) throw std::runtime_error("cannot open mesh OBJ: " + path);
  out << std::setprecision(17);
  for (const Vertex& vertex : mesh.vertices) {
    out << "v " << vertex.x << ' ' << vertex.y << ' ' << vertex.z << '\n';
  }
  for (const Triangle& triangle : mesh.faces) {
    out << "f " << triangle.v[0] + 1U << ' ' << triangle.v[1] + 1U
        << ' ' << triangle.v[2] + 1U << '\n';
  }
}

void write_failure_json(const Args& args, const std::string& stage,
                        const std::string& message, const double elapsed_seconds) {
  std::ofstream out(args.output);
  out << "{\n"
      << "  \"schema\": \"topic4.occt_step_preflight.v1\",\n"
      << "  \"corpus_id\": \"" << json_escape(args.corpus_id) << "\",\n"
      << "  \"source_group\": \"" << json_escape(args.source_group) << "\",\n"
      << "  \"input_path\": \"" << json_escape(args.input) << "\",\n"
      << "  \"tool_ok\": false,\n"
      << "  \"failure_stage\": \"" << json_escape(stage) << "\",\n"
      << "  \"failure_message\": \"" << json_escape(message) << "\",\n"
      << "  \"elapsed_seconds\": ";
  write_number(out, elapsed_seconds);
  out << "\n}\n";
}

}  // namespace

int main(int argc, char** argv) {
  Args args;
  const auto started = std::chrono::steady_clock::now();
  try {
    args = parse_args(argc, argv);
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 64;
  }

  try {
    STEPControl_Reader reader;
    const IFSelect_ReturnStatus status = reader.ReadFile(args.input.c_str());
    if (status != IFSelect_RetDone) {
      const double elapsed = std::chrono::duration<double>(
          std::chrono::steady_clock::now() - started).count();
      write_failure_json(args, "read", "STEPControl_Reader did not return IFSelect_RetDone", elapsed);
      return 10;
    }
    const int roots = reader.NbRootsForTransfer();
    const int transferred = reader.TransferRoots();
    if (transferred <= 0) {
      const double elapsed = std::chrono::duration<double>(
          std::chrono::steady_clock::now() - started).count();
      write_failure_json(args, "transfer", "no STEP roots transferred", elapsed);
      return 11;
    }
    const TopoDS_Shape shape = reader.OneShape();
    if (shape.IsNull()) {
      const double elapsed = std::chrono::duration<double>(
          std::chrono::steady_clock::now() - started).count();
      write_failure_json(args, "transfer", "transferred shape is null", elapsed);
      return 12;
    }

    TopoDS_Compound solid_subset;
    BRep_Builder builder;
    builder.MakeCompound(solid_subset);
    for (TopExp_Explorer it(shape, TopAbs_SOLID); it.More(); it.Next()) {
      builder.Add(solid_subset, it.Current());
    }

    Bnd_Box bbox;
    BRepBndLib::Add(solid_subset, bbox, true);
    double xmin = 0.0, ymin = 0.0, zmin = 0.0, xmax = 0.0, ymax = 0.0, zmax = 0.0;
    if (!bbox.IsVoid()) bbox.Get(xmin, ymin, zmin, xmax, ymax, zmax);
    const double dx = xmax - xmin, dy = ymax - ymin, dz = zmax - zmin;
    const double diagonal = std::sqrt(dx * dx + dy * dy + dz * dz);
    const double volume_epsilon = std::max(diagonal * diagonal * diagonal * 1.0e-15, 1.0e-18);

    const BRepCheck_Analyzer analyzer(shape, true);
    const bool shape_valid = analyzer.IsValid();
    int invalid_solids = 0;
    int invalid_shells = 0;
    int invalid_faces = 0;
    int solids = 0;
    int shells = 0;
    int closed_shells = 0;
    int open_shells = 0;
    const int full_shape_shells = count_subshapes(shape, TopAbs_SHELL);
    int full_shape_closed_shells = 0;
    int full_shape_open_shells = 0;
    for (TopExp_Explorer it(shape, TopAbs_SHELL); it.More(); it.Next()) {
      const TopoDS_Shell shell = TopoDS::Shell(it.Current());
      if (BRep_Tool::IsClosed(shell)) ++full_shape_closed_shells;
      else ++full_shape_open_shells;
    }
    int positive_volume_solids = 0;
    int nonpositive_volume_solids = 0;
    double total_signed_volume = 0.0;
    double total_absolute_volume = 0.0;

    for (TopExp_Explorer it(shape, TopAbs_SOLID); it.More(); it.Next()) {
      ++solids;
      const TopoDS_Solid solid = TopoDS::Solid(it.Current());
      if (!BRepCheck_Analyzer(solid, true).IsValid()) ++invalid_solids;
      for (TopExp_Explorer shell_it(solid, TopAbs_SHELL); shell_it.More(); shell_it.Next()) {
        ++shells;
        const TopoDS_Shell shell = TopoDS::Shell(shell_it.Current());
        if (!BRepCheck_Analyzer(shell, true).IsValid()) ++invalid_shells;
        if (BRep_Tool::IsClosed(shell)) ++closed_shells;
        else ++open_shells;
      }
      for (TopExp_Explorer face_it(solid, TopAbs_FACE); face_it.More(); face_it.Next()) {
        if (!BRepCheck_Analyzer(face_it.Current(), true).IsValid()) ++invalid_faces;
      }
      GProp_GProps properties;
      BRepGProp::VolumeProperties(solid, properties, true, false, false);
      const double volume = properties.Mass();
      total_signed_volume += volume;
      total_absolute_volume += std::abs(volume);
      if (std::isfinite(volume) && volume > volume_epsilon) ++positive_volume_solids;
      else ++nonpositive_volume_solids;
    }
    const MeshStats mesh = triangulate_and_audit(
        solid_subset, diagonal, args.relative_deflection, args.angular_deflection);
    write_obj(args.mesh_output, mesh);
    const bool brep_all_solids_positive = solids > 0 && nonpositive_volume_solids == 0;
    const bool brep_all_shells_closed = shells > 0 && open_shells == 0;
    const bool mesh_watertight = mesh.triangles > 0 && mesh.boundary_edges == 0;
    const bool mesh_edge_manifold = mesh.triangles > 0 && mesh.nonmanifold_edges == 0;
    const bool mesh_positive_volume = std::isfinite(mesh.signed_volume) && mesh.signed_volume > volume_epsilon;
    const bool solid_subset_valid = solids > 0 && invalid_solids == 0 && invalid_shells == 0 && invalid_faces == 0;
    const bool dc_admissible = solid_subset_valid &&
        invalid_faces == 0 && brep_all_solids_positive && brep_all_shells_closed &&
        mesh.meshing_done && mesh_watertight && mesh_edge_manifold && mesh_positive_volume;

    const double elapsed = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - started).count();
    std::ofstream out(args.output);
    if (!out) throw std::runtime_error("cannot open output JSON: " + args.output);
    out << "{\n"
        << "  \"schema\": \"topic4.occt_step_preflight.v1\",\n"
        << "  \"corpus_id\": \"" << json_escape(args.corpus_id) << "\",\n"
        << "  \"source_group\": \"" << json_escape(args.source_group) << "\",\n"
        << "  \"input_path\": \"" << json_escape(args.input) << "\",\n"
        << "  \"mesh_output_path\": "
        << (args.mesh_output.empty() ? "null" : ("\"" + json_escape(args.mesh_output) + "\"")) << ",\n"
        << "  \"tool_ok\": true,\n"
        << "  \"kernel\": {\"name\": \"OpenCascade\", \"version\": \"7.9.3\", \"draw_linked\": false},\n"
        << "  \"step\": {\"roots\": " << roots << ", \"transferred_roots\": " << transferred << "},\n"
        << "  \"topology\": {\n"
        << "    \"compounds\": " << count_subshapes(shape, TopAbs_COMPOUND) << ",\n"
        << "    \"compsolids\": " << count_subshapes(shape, TopAbs_COMPSOLID) << ",\n"
        << "    \"solids\": " << solids << ",\n"
        << "    \"shells\": " << shells << ",\n"
        << "    \"faces\": " << count_subshapes(shape, TopAbs_FACE) << ",\n"
        << "    \"edges\": " << count_subshapes(shape, TopAbs_EDGE) << ",\n"
        << "    \"vertices\": " << count_subshapes(shape, TopAbs_VERTEX) << "\n"
        << "  },\n"
        << "  \"validity\": {\n"
        << "    \"shape_valid\": " << (shape_valid ? "true" : "false") << ",\n"
        << "    \"solid_subset_valid\": " << (solid_subset_valid ? "true" : "false") << ",\n"
        << "    \"invalid_solids\": " << invalid_solids << ",\n"
        << "    \"invalid_shells\": " << invalid_shells << ",\n"
        << "    \"invalid_faces\": " << invalid_faces << "\n"
        << "  },\n"
        << "  \"full_shape_auxiliary\": {\"shells\": " << full_shape_shells
        << ", \"closed_shells\": " << full_shape_closed_shells
        << ", \"open_shells\": " << full_shape_open_shells
        << ", \"non_solid_shells\": " << (full_shape_shells - shells) << "},\n"
        << "  \"brep_closure\": {\"closed_shells\": " << closed_shells
        << ", \"open_shells\": " << open_shells
        << ", \"all_shells_closed\": " << (brep_all_shells_closed ? "true" : "false") << "},\n"
        << "  \"brep_volume\": {\n"
        << "    \"positive_solids\": " << positive_volume_solids << ",\n"
        << "    \"nonpositive_solids\": " << nonpositive_volume_solids << ",\n"
        << "    \"all_solids_positive\": " << (brep_all_solids_positive ? "true" : "false") << ",\n"
        << "    \"total_signed\": "; write_number(out, total_signed_volume); out << ",\n"
        << "    \"total_absolute\": "; write_number(out, total_absolute_volume); out << ",\n"
        << "    \"epsilon\": "; write_number(out, volume_epsilon); out << "\n"
        << "  },\n"
        << "  \"bbox\": {\"min\": [";
    write_number(out, xmin); out << ", "; write_number(out, ymin); out << ", "; write_number(out, zmin);
    out << "], \"max\": ["; write_number(out, xmax); out << ", "; write_number(out, ymax); out << ", "; write_number(out, zmax);
    out << "], \"diagonal\": "; write_number(out, diagonal); out << "},\n"
        << "  \"mesh\": {\n"
        << "    \"meshing_done\": " << (mesh.meshing_done ? "true" : "false") << ",\n"
        << "    \"raw_vertices\": " << mesh.raw_vertices << ",\n"
        << "    \"welded_vertices\": " << mesh.welded_vertices << ",\n"
        << "    \"triangles\": " << mesh.triangles << ",\n"
        << "    \"degenerate_triangles_removed\": " << mesh.degenerate_triangles << ",\n"
        << "    \"unique_edges\": " << mesh.unique_edges << ",\n"
        << "    \"boundary_edges\": " << mesh.boundary_edges << ",\n"
        << "    \"nonmanifold_edges\": " << mesh.nonmanifold_edges << ",\n"
        << "    \"connected_components\": " << mesh.connected_components << ",\n"
        << "    \"watertight\": " << (mesh_watertight ? "true" : "false") << ",\n"
        << "    \"edge_manifold\": " << (mesh_edge_manifold ? "true" : "false") << ",\n"
        << "    \"positive_signed_volume\": " << (mesh_positive_volume ? "true" : "false") << ",\n"
        << "    \"surface_area\": "; write_number(out, mesh.surface_area); out << ",\n"
        << "    \"signed_volume\": "; write_number(out, mesh.signed_volume); out << ",\n"
        << "    \"weld_tolerance\": "; write_number(out, mesh.weld_tolerance); out << "\n"
        << "  },\n"
        << "  \"admission\": {\"dual_contouring_candidate\": " << (dc_admissible ? "true" : "false") << "},\n"
        << "  \"elapsed_seconds\": "; write_number(out, elapsed); out << "\n"
        << "}\n";
    return 0;
  } catch (const Standard_Failure& error) {
    const double elapsed = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - started).count();
    const char* message = error.GetMessageString();
    write_failure_json(args, "occt_exception", message ? message : "OpenCascade Standard_Failure", elapsed);
    std::cerr << (message ? message : "OpenCascade Standard_Failure") << '\n';
    return 20;
  } catch (const std::exception& error) {
    const double elapsed = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - started).count();
    write_failure_json(args, "exception", error.what(), elapsed);
    std::cerr << error.what() << '\n';
    return 21;
  } catch (...) {
    const double elapsed = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - started).count();
    write_failure_json(args, "unknown_exception", "unknown exception", elapsed);
    return 22;
  }
}
