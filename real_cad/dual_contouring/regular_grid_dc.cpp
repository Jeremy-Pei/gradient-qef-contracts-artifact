#include <Eigen/Core>
#include <Eigen/Eigenvalues>
#include <Eigen/SVD>
#include <igl/signed_distance.h>

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
#include <tuple>
#include <utility>
#include <vector>

namespace {

using Vec3 = Eigen::Vector3d;

struct Args {
  std::string input;
  std::string output;
  std::string baseline_obj;
  std::string fallback_obj;
  std::string corpus_id;
  int resolution = 32;
  int padding = 2;
  double lambda = 1.0e-4;
  double tau_cell = 0.10;
};

struct Tri { std::array<int, 3> v{}; };
struct Mesh { std::vector<Vec3> vertices; std::vector<Tri> faces; };

struct RootSample {
  Vec3 approximate_point = Vec3::Zero();
  Vec3 approximate_normal = Vec3::Zero();
  Vec3 oracle_point = Vec3::Zero();
  Vec3 oracle_normal = Vec3::Zero();
};

struct Cell {
  bool active = false;
  bool certified = false;
  bool outside_cell = false;
  int root_begin = 0;
  int root_count = 0;
  Vec3 center = Vec3::Zero();
  Vec3 baseline_vertex = Vec3::Zero();
  Vec3 oracle_vertex = Vec3::Zero();
  Vec3 fallback_vertex = Vec3::Zero();
  double measured_displacement = 0.0;
  double qef_bound = 0.0;
};

struct MeshAudit {
  std::size_t vertices = 0;
  std::size_t triangles = 0;
  std::size_t degenerate_triangles = 0;
  std::size_t boundary_edges = 0;
  std::size_t nonmanifold_edges = 0;
  double signed_volume = 0.0;
  double mean_abs_surface_distance = 0.0;
  double max_abs_surface_distance = 0.0;
};

std::string escape_json(const std::string& value) {
  std::ostringstream out;
  for (const unsigned char c : value) {
    switch (c) {
      case '\"': out << "\\\""; break;
      case '\\': out << "\\\\"; break;
      case '\n': out << "\\n"; break;
      case '\r': out << "\\r"; break;
      case '\t': out << "\\t"; break;
      default:
        if (c < 0x20) out << "?";
        else out << c;
    }
  }
  return out.str();
}

void number(std::ostream& out, const double value) {
  if (std::isfinite(value)) out << std::setprecision(17) << value;
  else out << "null";
}

Args parse_args(const int argc, char** argv) {
  Args args;
  for (int i = 1; i < argc; ++i) {
    const std::string key = argv[i];
    auto value = [&]() {
      if (i + 1 >= argc) throw std::runtime_error("missing value after " + key);
      return std::string(argv[++i]);
    };
    if (key == "--input") args.input = value();
    else if (key == "--output") args.output = value();
    else if (key == "--baseline-obj") args.baseline_obj = value();
    else if (key == "--fallback-obj") args.fallback_obj = value();
    else if (key == "--id") args.corpus_id = value();
    else if (key == "--resolution") args.resolution = std::stoi(value());
    else if (key == "--padding") args.padding = std::stoi(value());
    else if (key == "--lambda") args.lambda = std::stod(value());
    else if (key == "--tau-cell") args.tau_cell = std::stod(value());
    else throw std::runtime_error("unknown argument: " + key);
  }
  if (args.input.empty() || args.output.empty() || args.corpus_id.empty())
    throw std::runtime_error("required: --input OBJ --output JSON --id ID");
  if (args.resolution < 8 || args.padding < 1 || args.lambda <= 0.0 || args.tau_cell <= 0.0)
    throw std::runtime_error("invalid resolution, padding, lambda, or tolerance");
  return args;
}

Mesh read_obj(const std::string& path) {
  std::ifstream in(path);
  if (!in) throw std::runtime_error("cannot read OBJ: " + path);
  Mesh mesh;
  std::string line;
  while (std::getline(in, line)) {
    std::istringstream row(line);
    std::string kind;
    row >> kind;
    if (kind == "v") {
      Vec3 v;
      row >> v.x() >> v.y() >> v.z();
      if (!row.fail()) mesh.vertices.push_back(v);
    } else if (kind == "f") {
      Tri tri;
      std::string token;
      bool ok = true;
      for (int i = 0; i < 3; ++i) {
        if (!(row >> token)) { ok = false; break; }
        const auto slash = token.find('/');
        if (slash != std::string::npos) token.resize(slash);
        tri.v[i] = std::stoi(token) - 1;
      }
      if (ok) mesh.faces.push_back(tri);
    }
  }
  if (mesh.vertices.empty() || mesh.faces.empty()) throw std::runtime_error("empty OBJ mesh");
  return mesh;
}

void write_obj(const std::string& path, const std::vector<Vec3>& vertices,
               const std::vector<Tri>& faces) {
  if (path.empty()) return;
  std::ofstream out(path);
  if (!out) throw std::runtime_error("cannot write OBJ: " + path);
  out << std::setprecision(17);
  for (const Vec3& v : vertices) out << "v " << v.x() << ' ' << v.y() << ' ' << v.z() << '\n';
  for (const Tri& f : faces) out << "f " << f.v[0] + 1 << ' ' << f.v[1] + 1 << ' ' << f.v[2] + 1 << '\n';
}

double quantile(std::vector<double> values, const double q) {
  if (values.empty()) return std::numeric_limits<double>::quiet_NaN();
  std::sort(values.begin(), values.end());
  const double position = q * static_cast<double>(values.size() - 1);
  const std::size_t lower = static_cast<std::size_t>(std::floor(position));
  const std::size_t upper = static_cast<std::size_t>(std::ceil(position));
  const double t = position - static_cast<double>(lower);
  return (1.0 - t) * values[lower] + t * values[upper];
}

struct Grid {
  int nx = 0, ny = 0, nz = 0;
  double h = 0.0;
  Vec3 origin = Vec3::Zero();
  std::vector<double> sdf;
  std::vector<Vec3> gradient;
  std::size_t node_index(int i, int j, int k) const {
    return static_cast<std::size_t>(i) + static_cast<std::size_t>(nx) *
        (static_cast<std::size_t>(j) + static_cast<std::size_t>(ny) * static_cast<std::size_t>(k));
  }
  std::size_t cell_index(int i, int j, int k) const {
    return static_cast<std::size_t>(i) + static_cast<std::size_t>(nx - 1) *
        (static_cast<std::size_t>(j) + static_cast<std::size_t>(ny - 1) * static_cast<std::size_t>(k));
  }
  Vec3 point(int i, int j, int k) const { return origin + h * Vec3(i, j, k); }
};

Grid build_grid(const Eigen::MatrixXd& V, const Eigen::MatrixXi& F,
                const int resolution, const int padding) {
  const Vec3 minimum = V.colwise().minCoeff();
  const Vec3 maximum = V.colwise().maxCoeff();
  const Vec3 extent = maximum - minimum;
  const double max_extent = extent.maxCoeff();
  if (!(max_extent > 0.0)) throw std::runtime_error("degenerate mesh bounds");
  Grid grid;
  grid.h = max_extent / static_cast<double>(resolution);
  grid.origin = minimum - static_cast<double>(padding) * grid.h * Vec3::Ones();
  const Vec3 padded_extent = extent + 2.0 * static_cast<double>(padding) * grid.h * Vec3::Ones();
  grid.nx = static_cast<int>(std::ceil(padded_extent.x() / grid.h)) + 1;
  grid.ny = static_cast<int>(std::ceil(padded_extent.y() / grid.h)) + 1;
  grid.nz = static_cast<int>(std::ceil(padded_extent.z() / grid.h)) + 1;
  const Eigen::Index count = static_cast<Eigen::Index>(grid.nx) * grid.ny * grid.nz;
  Eigen::MatrixXd P(count, 3);
  Eigen::Index row = 0;
  for (int k = 0; k < grid.nz; ++k)
    for (int j = 0; j < grid.ny; ++j)
      for (int i = 0; i < grid.nx; ++i) P.row(row++) = grid.point(i, j, k);
  Eigen::VectorXd S;
  Eigen::VectorXi I;
  Eigen::MatrixXd C, N;
  igl::signed_distance(P, V, F, igl::SIGNED_DISTANCE_TYPE_FAST_WINDING_NUMBER, S, I, C, N);
  grid.sdf.resize(static_cast<std::size_t>(count));
  for (Eigen::Index i = 0; i < count; ++i) grid.sdf[static_cast<std::size_t>(i)] = S(i);
  grid.gradient.resize(static_cast<std::size_t>(count), Vec3::Zero());
  auto derivative = [&](int i0, int i1, int j, int k, int axis) {
    (void)axis;
    return (grid.sdf[grid.node_index(i1, j, k)] - grid.sdf[grid.node_index(i0, j, k)]) /
        (static_cast<double>(i1 - i0) * grid.h);
  };
  for (int k = 0; k < grid.nz; ++k) {
    for (int j = 0; j < grid.ny; ++j) {
      for (int i = 0; i < grid.nx; ++i) {
        const int im = std::max(i - 1, 0), ip = std::min(i + 1, grid.nx - 1);
        const int jm = std::max(j - 1, 0), jp = std::min(j + 1, grid.ny - 1);
        const int km = std::max(k - 1, 0), kp = std::min(k + 1, grid.nz - 1);
        Vec3 g;
        g.x() = derivative(im, ip, j, k, 0);
        g.y() = (grid.sdf[grid.node_index(i, jp, k)] - grid.sdf[grid.node_index(i, jm, k)]) /
            (static_cast<double>(jp - jm) * grid.h);
        g.z() = (grid.sdf[grid.node_index(i, j, kp)] - grid.sdf[grid.node_index(i, j, km)]) /
            (static_cast<double>(kp - km) * grid.h);
        grid.gradient[grid.node_index(i, j, k)] = g;
      }
    }
  }
  return grid;
}

std::pair<Vec3, Vec3> solve_qef(const std::vector<RootSample>& roots, const Cell& cell,
                                const bool oracle, const double lambda) {
  Eigen::MatrixXd N(roots.size(), 3);
  Eigen::VectorXd h(roots.size());
  for (std::size_t i = 0; i < roots.size(); ++i) {
    const Vec3 n = oracle ? roots[i].oracle_normal : roots[i].approximate_normal;
    const Vec3 p = oracle ? roots[i].oracle_point : roots[i].approximate_point;
    N.row(static_cast<Eigen::Index>(i)) = n;
    h(static_cast<Eigen::Index>(i)) = n.dot(p - cell.center);
  }
  const Eigen::Matrix3d H = N.transpose() * N + lambda * Eigen::Matrix3d::Identity();
  const Vec3 q = N.transpose() * h;
  return {H.ldlt().solve(q), q};
}

void append_quad(std::vector<Tri>& faces, const std::array<int, 4>& quad, const bool flip) {
  if (!flip) {
    faces.push_back({{quad[0], quad[1], quad[2]}});
    faces.push_back({{quad[0], quad[2], quad[3]}});
  } else {
    faces.push_back({{quad[0], quad[2], quad[1]}});
    faces.push_back({{quad[0], quad[3], quad[2]}});
  }
}

MeshAudit audit_mesh(const std::vector<Vec3>& vertices, const std::vector<Tri>& faces,
                     const Eigen::MatrixXd& source_v, const Eigen::MatrixXi& source_f) {
  MeshAudit audit;
  audit.vertices = vertices.size();
  audit.triangles = faces.size();
  std::map<std::pair<int, int>, int> edges;
  for (const Tri& f : faces) {
    const Vec3& a = vertices[f.v[0]];
    const Vec3& b = vertices[f.v[1]];
    const Vec3& c = vertices[f.v[2]];
    const Vec3 cross = (b - a).cross(c - a);
    if (cross.squaredNorm() <= 1.0e-28) ++audit.degenerate_triangles;
    audit.signed_volume += a.dot(b.cross(c)) / 6.0;
    for (int e = 0; e < 3; ++e) {
      int u = f.v[e], v = f.v[(e + 1) % 3];
      if (u > v) std::swap(u, v);
      ++edges[{u, v}];
    }
  }
  for (const auto& [edge, count] : edges) {
    (void)edge;
    if (count == 1) ++audit.boundary_edges;
    else if (count > 2) ++audit.nonmanifold_edges;
  }
  if (!vertices.empty()) {
    Eigen::MatrixXd P(vertices.size(), 3);
    for (std::size_t i = 0; i < vertices.size(); ++i) P.row(static_cast<Eigen::Index>(i)) = vertices[i];
    Eigen::VectorXd S;
    Eigen::VectorXi I;
    Eigen::MatrixXd C, N;
    igl::signed_distance(P, source_v, source_f, igl::SIGNED_DISTANCE_TYPE_UNSIGNED, S, I, C, N);
    double total = 0.0;
    for (Eigen::Index i = 0; i < S.size(); ++i) {
      const double distance = std::abs(S(i));
      total += distance;
      audit.max_abs_surface_distance = std::max(audit.max_abs_surface_distance, distance);
    }
    audit.mean_abs_surface_distance = total / static_cast<double>(S.size());
  }
  return audit;
}

void write_audit(std::ostream& out, const MeshAudit& audit, const double h) {
  out << "{\"vertices\": " << audit.vertices
      << ", \"triangles\": " << audit.triangles
      << ", \"degenerate_triangles\": " << audit.degenerate_triangles
      << ", \"boundary_edges\": " << audit.boundary_edges
      << ", \"nonmanifold_edges\": " << audit.nonmanifold_edges
      << ", \"signed_volume\": "; number(out, audit.signed_volume);
  out << ", \"mean_abs_surface_distance\": "; number(out, audit.mean_abs_surface_distance);
  out << ", \"max_abs_surface_distance\": "; number(out, audit.max_abs_surface_distance);
  out << ", \"mean_abs_surface_distance_cell_units\": "; number(out, audit.mean_abs_surface_distance / h);
  out << ", \"max_abs_surface_distance_cell_units\": "; number(out, audit.max_abs_surface_distance / h);
  out << '}';
}

}  // namespace

int main(int argc, char** argv) {
  const auto started = std::chrono::steady_clock::now();
  Args args;
  try {
    args = parse_args(argc, argv);
    const Mesh source = read_obj(args.input);
    Eigen::MatrixXd V(source.vertices.size(), 3);
    Eigen::MatrixXi F(source.faces.size(), 3);
    for (std::size_t i = 0; i < source.vertices.size(); ++i) V.row(static_cast<Eigen::Index>(i)) = source.vertices[i];
    for (std::size_t i = 0; i < source.faces.size(); ++i)
      for (int j = 0; j < 3; ++j) F(static_cast<Eigen::Index>(i), j) = source.faces[i].v[j];

    const Grid grid = build_grid(V, F, args.resolution, args.padding);
    const int cx = grid.nx - 1, cy = grid.ny - 1, cz = grid.nz - 1;
    std::vector<Cell> cells(static_cast<std::size_t>(cx) * cy * cz);
    std::vector<RootSample> roots;
    const std::array<std::array<int, 3>, 8> corner_offset{{
      {{0,0,0}}, {{1,0,0}}, {{1,1,0}}, {{0,1,0}},
      {{0,0,1}}, {{1,0,1}}, {{1,1,1}}, {{0,1,1}}
    }};
    const std::array<std::array<int, 2>, 12> edge_corners{{
      {{0,1}}, {{1,2}}, {{2,3}}, {{3,0}}, {{4,5}}, {{5,6}},
      {{6,7}}, {{7,4}}, {{0,4}}, {{1,5}}, {{2,6}}, {{3,7}}
    }};
    for (int k = 0; k < cz; ++k) for (int j = 0; j < cy; ++j) for (int i = 0; i < cx; ++i) {
      std::array<double, 8> s{};
      bool has_negative = false, has_nonnegative = false;
      for (int c = 0; c < 8; ++c) {
        const auto& o = corner_offset[c];
        s[c] = grid.sdf[grid.node_index(i + o[0], j + o[1], k + o[2])];
        has_negative = has_negative || s[c] < 0.0;
        has_nonnegative = has_nonnegative || s[c] >= 0.0;
      }
      if (!(has_negative && has_nonnegative)) continue;
      Cell& cell = cells[grid.cell_index(i, j, k)];
      cell.active = true;
      cell.center = grid.point(i, j, k) + 0.5 * grid.h * Vec3::Ones();
      cell.root_begin = static_cast<int>(roots.size());
      for (const auto& edge : edge_corners) {
        const int a = edge[0], b = edge[1];
        if ((s[a] < 0.0) == (s[b] < 0.0)) continue;
        const double denominator = s[a] - s[b];
        if (std::abs(denominator) <= 1.0e-30) continue;
        const double t = std::clamp(s[a] / denominator, 0.0, 1.0);
        const auto& oa = corner_offset[a];
        const auto& ob = corner_offset[b];
        const Vec3 pa = grid.point(i + oa[0], j + oa[1], k + oa[2]);
        const Vec3 pb = grid.point(i + ob[0], j + ob[1], k + ob[2]);
        Vec3 g = (1.0 - t) * grid.gradient[grid.node_index(i + oa[0], j + oa[1], k + oa[2])] +
            t * grid.gradient[grid.node_index(i + ob[0], j + ob[1], k + ob[2])];
        if (!(g.norm() > 1.0e-12)) continue;
        g.normalize();
        RootSample root;
        root.approximate_point = (1.0 - t) * pa + t * pb;
        root.approximate_normal = g;
        roots.push_back(root);
      }
      cell.root_count = static_cast<int>(roots.size()) - cell.root_begin;
      if (cell.root_count < 3) cell.active = false;
    }

    if (roots.empty()) throw std::runtime_error("no Hermite roots generated");
    Eigen::MatrixXd root_queries(roots.size(), 3);
    for (std::size_t i = 0; i < roots.size(); ++i) root_queries.row(static_cast<Eigen::Index>(i)) = roots[i].approximate_point;
    Eigen::VectorXd oracle_s;
    Eigen::VectorXi oracle_i;
    Eigen::MatrixXd oracle_c, oracle_n;
    igl::signed_distance(root_queries, V, F, igl::SIGNED_DISTANCE_TYPE_PSEUDONORMAL,
                         oracle_s, oracle_i, oracle_c, oracle_n);
    for (std::size_t i = 0; i < roots.size(); ++i) {
      roots[i].oracle_point = oracle_c.row(static_cast<Eigen::Index>(i));
      roots[i].oracle_normal = oracle_n.row(static_cast<Eigen::Index>(i));
      if (!(roots[i].oracle_normal.norm() > 1.0e-12)) roots[i].oracle_normal = roots[i].approximate_normal;
      else roots[i].oracle_normal.normalize();
      if (roots[i].oracle_normal.dot(roots[i].approximate_normal) < 0.0) roots[i].oracle_normal *= -1.0;
    }

    std::vector<double> root_normal_angle_degrees;
    std::vector<double> root_position_error_cell_units;
    root_normal_angle_degrees.reserve(roots.size());
    root_position_error_cell_units.reserve(roots.size());
    for (const RootSample& root : roots) {
      const double cosine = std::clamp(root.approximate_normal.dot(root.oracle_normal), -1.0, 1.0);
      root_normal_angle_degrees.push_back(std::acos(cosine) * 180.0 / std::acos(-1.0));
      root_position_error_cell_units.push_back(
          (root.approximate_point - root.oracle_point).norm() / grid.h);
    }

    std::vector<double> bounds_cell, measured_cell;
    std::size_t active_count = 0, certified_count = 0, bound_violations = 0, outside_count = 0;
    for (Cell& cell : cells) {
      if (!cell.active) continue;
      ++active_count;
      std::vector<RootSample> local(roots.begin() + cell.root_begin,
                                    roots.begin() + cell.root_begin + cell.root_count);
      const auto [yhat, qhat] = solve_qef(local, cell, false, args.lambda);
      const auto [ytrue, qtrue] = solve_qef(local, cell, true, args.lambda);
      (void)qtrue;
      cell.baseline_vertex = cell.center + yhat;
      cell.oracle_vertex = cell.center + ytrue;
      cell.measured_displacement = (yhat - ytrue).norm();
      Eigen::MatrixXd Nhat(local.size(), 3);
      Eigen::VectorXd hhat(local.size());
      double eta_n_sq = 0.0, eta_h_sq = 0.0;
      const double radius = std::sqrt(3.0) * 0.5 * grid.h;
      for (std::size_t r = 0; r < local.size(); ++r) {
        const double eta_n = (local[r].approximate_normal - local[r].oracle_normal).norm();
        const double eta_p = (local[r].approximate_point - local[r].oracle_point).norm();
        const double eta_h = eta_p + radius * eta_n;
        eta_n_sq += eta_n * eta_n;
        eta_h_sq += eta_h * eta_h;
        Nhat.row(static_cast<Eigen::Index>(r)) = local[r].approximate_normal;
        hhat(static_cast<Eigen::Index>(r)) = local[r].approximate_normal.dot(local[r].approximate_point - cell.center);
      }
      const double eta_N = std::sqrt(eta_n_sq);
      const double E_h = std::sqrt(eta_h_sq);
      const double norm_N = Nhat.jacobiSvd().singularValues()(0);
      const double eta_H = 2.0 * norm_N * eta_N + eta_N * eta_N;
      const double eta_q = norm_N * E_h + eta_N * hhat.norm() + eta_N * E_h;
      const Eigen::Matrix3d Hhat = Nhat.transpose() * Nhat + args.lambda * Eigen::Matrix3d::Identity();
      const double lambda_min = Eigen::SelfAdjointEigenSolver<Eigen::Matrix3d>(Hhat).eigenvalues().minCoeff();
      const double gamma = std::max(args.lambda, lambda_min - eta_H);
      cell.qef_bound = (eta_H * yhat.norm() + eta_q) / gamma;
      cell.certified = std::isfinite(cell.qef_bound) && cell.qef_bound / grid.h <= args.tau_cell;
      cell.fallback_vertex = cell.certified ? cell.baseline_vertex : cell.center;
      const Vec3 low = cell.center - 0.5 * grid.h * Vec3::Ones();
      const Vec3 high = cell.center + 0.5 * grid.h * Vec3::Ones();
      cell.outside_cell = (cell.baseline_vertex.array() < low.array()).any() || (cell.baseline_vertex.array() > high.array()).any();
      if (cell.outside_cell) ++outside_count;
      if (cell.certified) ++certified_count;
      if (cell.measured_displacement > cell.qef_bound + 1.0e-10 * grid.h) ++bound_violations;
      bounds_cell.push_back(cell.qef_bound / grid.h);
      measured_cell.push_back(cell.measured_displacement / grid.h);
    }

    std::vector<Vec3> baseline_vertices, fallback_vertices;
    std::vector<int> vertex_index(cells.size(), -1);
    for (std::size_t index = 0; index < cells.size(); ++index) {
      if (!cells[index].active) continue;
      vertex_index[index] = static_cast<int>(baseline_vertices.size());
      baseline_vertices.push_back(cells[index].baseline_vertex);
      fallback_vertices.push_back(cells[index].fallback_vertex);
    }
    auto cidx = [&](int i, int j, int k) { return grid.cell_index(i, j, k); };
    std::vector<Tri> dc_faces;
    auto add_if_valid = [&](const std::array<std::size_t, 4>& cell_ids, bool flip) {
      std::array<int, 4> quad{};
      for (int q = 0; q < 4; ++q) {
        quad[q] = vertex_index[cell_ids[q]];
        if (quad[q] < 0) return;
      }
      append_quad(dc_faces, quad, flip);
    };
    for (int k = 1; k < grid.nz - 1; ++k) for (int j = 1; j < grid.ny - 1; ++j) for (int i = 0; i < grid.nx - 1; ++i) {
      const double a = grid.sdf[grid.node_index(i,j,k)], b = grid.sdf[grid.node_index(i+1,j,k)];
      if ((a < 0.0) != (b < 0.0)) add_if_valid({cidx(i,j-1,k-1),cidx(i,j,k-1),cidx(i,j,k),cidx(i,j-1,k)}, !(a < 0.0));
    }
    for (int k = 1; k < grid.nz - 1; ++k) for (int j = 0; j < grid.ny - 1; ++j) for (int i = 1; i < grid.nx - 1; ++i) {
      const double a = grid.sdf[grid.node_index(i,j,k)], b = grid.sdf[grid.node_index(i,j+1,k)];
      if ((a < 0.0) != (b < 0.0)) add_if_valid({cidx(i-1,j,k-1),cidx(i-1,j,k),cidx(i,j,k),cidx(i,j,k-1)}, !(a < 0.0));
    }
    for (int k = 0; k < grid.nz - 1; ++k) for (int j = 1; j < grid.ny - 1; ++j) for (int i = 1; i < grid.nx - 1; ++i) {
      const double a = grid.sdf[grid.node_index(i,j,k)], b = grid.sdf[grid.node_index(i,j,k+1)];
      if ((a < 0.0) != (b < 0.0)) add_if_valid({cidx(i-1,j-1,k),cidx(i,j-1,k),cidx(i,j,k),cidx(i-1,j,k)}, !(a < 0.0));
    }

    const MeshAudit baseline_audit = audit_mesh(baseline_vertices, dc_faces, V, F);
    const MeshAudit fallback_audit = audit_mesh(fallback_vertices, dc_faces, V, F);
    write_obj(args.baseline_obj, baseline_vertices, dc_faces);
    write_obj(args.fallback_obj, fallback_vertices, dc_faces);

    const double elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
    std::ofstream out(args.output);
    if (!out) throw std::runtime_error("cannot write JSON: " + args.output);
    out << "{\n"
        << "  \"schema\": \"topic4.regular_grid_dc.v1\",\n"
        << "  \"corpus_id\": \"" << escape_json(args.corpus_id) << "\",\n"
        << "  \"tool_ok\": true,\n"
        << "  \"method\": \"uniform-grid dual contouring with regularized per-cell QEF\",\n"
        << "  \"contract_semantics\": \"oracle diagnostic only; measured mesh projection and normal errors are not deployable upstream certificates\",\n"
        << "  \"configuration\": {\"resolution\": " << args.resolution
        << ", \"padding_voxels\": " << args.padding << ", \"lambda\": "; number(out, args.lambda);
    out << ", \"tau_cell_units\": "; number(out, args.tau_cell); out << "},\n"
        << "  \"grid\": {\"nx\": " << grid.nx << ", \"ny\": " << grid.ny << ", \"nz\": " << grid.nz
        << ", \"voxel_size\": "; number(out, grid.h); out << "},\n"
        << "  \"source_mesh\": {\"vertices\": " << source.vertices.size() << ", \"triangles\": " << source.faces.size() << "},\n"
        << "  \"qef\": {\n"
        << "    \"active_cells\": " << active_count << ",\n"
        << "    \"certified_oracle_diagnostic\": " << certified_count << ",\n"
        << "    \"unknown_oracle_diagnostic\": " << (active_count - certified_count) << ",\n"
        << "    \"coverage\": "; number(out, active_count ? static_cast<double>(certified_count)/active_count : 0.0); out << ",\n"
        << "    \"bound_violations\": " << bound_violations << ",\n"
        << "    \"outside_cell_vertices\": " << outside_count << ",\n"
        << "    \"median_normal_angle_error_degrees\": "; number(out, quantile(root_normal_angle_degrees, 0.5)); out << ",\n"
        << "    \"p95_normal_angle_error_degrees\": "; number(out, quantile(root_normal_angle_degrees, 0.95)); out << ",\n"
        << "    \"median_root_position_error_cell_units\": "; number(out, quantile(root_position_error_cell_units, 0.5)); out << ",\n"
        << "    \"p95_root_position_error_cell_units\": "; number(out, quantile(root_position_error_cell_units, 0.95)); out << ",\n"
        << "    \"median_bound_cell_units\": "; number(out, quantile(bounds_cell, 0.5)); out << ",\n"
        << "    \"p95_bound_cell_units\": "; number(out, quantile(bounds_cell, 0.95)); out << ",\n"
        << "    \"median_measured_displacement_cell_units\": "; number(out, quantile(measured_cell, 0.5)); out << ",\n"
        << "    \"p95_measured_displacement_cell_units\": "; number(out, quantile(measured_cell, 0.95)); out << "\n"
        << "  },\n"
        << "  \"baseline_mesh\": "; write_audit(out, baseline_audit, grid.h); out << ",\n"
        << "  \"contract_fallback_mesh\": "; write_audit(out, fallback_audit, grid.h); out << ",\n"
        << "  \"elapsed_seconds\": "; number(out, elapsed); out << "\n"
        << "}\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    if (!args.output.empty()) {
      std::ofstream out(args.output);
      out << "{\"schema\": \"topic4.regular_grid_dc.v1\", \"corpus_id\": \""
          << escape_json(args.corpus_id) << "\", \"tool_ok\": false, \"failure_message\": \""
          << escape_json(error.what()) << "\"}\n";
    }
    return 20;
  }
}
