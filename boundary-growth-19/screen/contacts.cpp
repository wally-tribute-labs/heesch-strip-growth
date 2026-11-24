// Exact local contact support for free polyhexes. A zero at depth D excludes
// a D-ring patch even when its last ring is allowed to enclose empty cells.
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <limits>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <vector>

using Word = uint64_t;
using Cell = std::pair<int, int>;
using Shape = std::vector<Cell>;
using Bits = std::vector<Word>;
constexpr int stride = 128;
constexpr int offset = 48;
constexpr int board = stride * stride;
const Shape steps{{1, 0}, {0, 1}, {-1, 1}, {-1, 0}, {0, -1}, {1, -1}};
Cell plus(Cell a, Cell b) { return {a.first + b.first, a.second + b.second}; }
Cell minus(Cell a, Cell b) { return {a.first - b.first, a.second - b.second}; }
int location(Cell a) {
    int x = a.first + offset, y = a.second + offset;
    if (x < 0 || x >= stride || y < 0 || y >= stride)
        throw std::runtime_error("spatial index exceeds contact board");
    return x * stride + y;
}
int count(Word w) { return __builtin_popcountll(w); }
int low(Word w) { return __builtin_ctzll(w); }
bool contains(const Bits &b, int i) { return b[i / 64] & (Word(1) << (i % 64)); }
void add(Bits &b, int i) { b[i / 64] |= Word(1) << (i % 64); }
struct Matrix {
    int a, b, c, d;
    Cell apply(Cell p) const { return {a * p.first + b * p.second, c * p.first + d * p.second}; }
    Matrix times(Matrix m) const {
        return {a * m.a + b * m.c, a * m.b + b * m.d, c * m.a + d * m.c, c * m.b + d * m.d};
    }
    bool operator==(Matrix m) const { return a == m.a && b == m.b && c == m.c && d == m.d; }
};
struct Group {
    std::array<Matrix, 12> matrices;
    int inverse[12], product[12][12];
    Group() {
        Matrix rotate{0, -1, 1, 1};
        for (int flip = 0; flip < 2; ++flip) {
            Matrix m = flip ? Matrix{0, 1, 1, 0} : Matrix{1, 0, 0, 1};
            for (int k = 0; k < 6; ++k) {
                matrices[6 * flip + k] = m;
                m = rotate.times(m);
            }
        }
        for (int i = 0; i < 12; ++i)
            for (int j = 0; j < 12; ++j) {
                int k =
                    std::find(matrices.begin(), matrices.end(), matrices[i].times(matrices[j])) -
                    matrices.begin();
                if (k >= 12)
                    throw std::runtime_error("unclosed orientation group");
                product[i][j] = k;
                if (k == 0)
                    inverse[i] = j;
            }
    }
};
const Group group;
Cell normalize(Shape &cells) {
    int x = cells[0].first, y = cells[0].second;
    for (auto p : cells) {
        x = std::min(x, p.first);
        y = std::min(y, p.second);
    }
    for (auto &p : cells)
        p = minus(p, {x, y});
    std::sort(cells.begin(), cells.end());
    return {-x, -y};
}
Shape boundary(const Shape &tile) {
    std::set<Cell> candidates;
    for (auto p : tile)
        for (auto d : steps)
            candidates.insert(plus(p, d));
    for (auto p : tile)
        candidates.erase(p);
    return Shape(candidates.begin(), candidates.end());
}
struct Pose {
    int sym;
    Cell origin;
    Word cover;
};
struct Limit {};
struct Search {
    Shape center, rim;
    std::array<Shape, 12> images;
    std::array<Cell, 12> shifts;
    int canonical[12];
    std::vector<Pose> poses;
    std::vector<int> lookup;
    std::vector<Bits> required, conflict;
    int words = 0;
    uint64_t nodes = 0, node_limit;
    Word all_needed;
    Bits found;
    std::vector<int> chosen;
    explicit Search(Shape tile, uint64_t budget) : center(std::move(tile)), node_limit(budget) {
        normalize(center);
        rim = boundary(center);
        if (rim.size() >= 64)
            throw std::runtime_error("halo reaches 64-bit mask limit");
        all_needed = (Word(1) << rim.size()) - 1;
        for (int i = 0; i < 12; ++i) {
            for (auto p : center)
                images[i].push_back(group.matrices[i].apply(p));
            shifts[i] = normalize(images[i]);
            canonical[i] = i;
            for (int j = 0; j < i; ++j)
                if (images[i] == images[j]) {
                    canonical[i] = j;
                    break;
                }
            if (canonical[i] != i)
                continue;
            std::array<bool, board> blocked{};
            for (auto p : center)
                for (auto q : images[i])
                    blocked[location(minus(p, q))] = true;
            std::array<Word, board> cover{};
            for (size_t h = 0; h < rim.size(); ++h)
                for (auto q : images[i]) {
                    auto t = minus(rim[h], q);
                    int pos = location(t);
                    if (!blocked[pos])
                        cover[pos] |= Word(1) << h;
                }
            for (int k = 0; k < board; ++k)
                if (cover[k]) {
                    Cell t{k / stride - offset, k % stride - offset};
                    poses.push_back({i, plus(t, shifts[i]), cover[k]});
                }
        }
        words = (poses.size() + 63) / 64;
        required.assign(rim.size(), Bits(words));
        for (size_t i = 0; i < poses.size(); ++i) {
            Word cover = poses[i].cover;
            while (cover) {
                add(required[low(cover)], i);
                cover &= cover - 1;
            }
        }
    }
    void build_conflicts() {
        std::vector<Word> owners(board * words);
        for (size_t i = 0; i < poses.size(); ++i) {
            auto p = poses[i];
            Cell t = minus(p.origin, shifts[p.sym]);
            for (auto c : images[p.sym])
                owners[location(plus(c, t)) * words + i / 64] |= Word(1) << (i % 64);
        }
        conflict.assign(poses.size(), Bits(words));
        for (size_t i = 0; i < poses.size(); ++i) {
            auto p = poses[i];
            Cell t = minus(p.origin, shifts[p.sym]);
            for (auto c : images[p.sym]) {
                auto start = owners.begin() + location(plus(c, t)) * words;
                for (int w = 0; w < words; ++w)
                    conflict[i][w] |= start[w];
            }
        }
    }
    bool visit(const Bits &allowed, Word remaining) {
        if (++nodes > node_limit)
            throw Limit();
        if (!remaining) {
            for (int p : chosen)
                add(found, p);
            return true;
        }
        int best = -1, minimum = std::numeric_limits<int>::max();
        for (Word r = remaining; r; r &= r - 1) {
            int h = low(r), n = 0;
            for (int w = 0; w < words && n < minimum; ++w)
                n += count(required[h][w] & allowed[w]);
            if (!n)
                return false;
            if (n < minimum) {
                minimum = n;
                best = h;
            }
        }
        for (int w = 0; w < words; ++w)
            for (Word v = required[best][w] & allowed[w]; v; v &= v - 1) {
                int j = w * 64 + low(v);
                Bits next(words);
                for (int u = 0; u < words; ++u)
                    next[u] = allowed[u] & ~conflict[j][u];
                chosen.push_back(j);
                bool yes = visit(next, remaining & ~poses[j].cover);
                chosen.pop_back();
                if (yes)
                    return true;
            }
        return false;
    }
    Bits support(const Bits &eligible) {
        found.assign(words, 0);
        if (!visit(eligible, all_needed))
            return found;
        for (size_t i = 0; i < poses.size(); ++i)
            if (contains(eligible, i) && !contains(found, i)) {
                Bits next(words);
                for (int w = 0; w < words; ++w)
                    next[w] = eligible[w] & ~conflict[i][w];
                chosen.push_back(i);
                visit(next, all_needed & ~poses[i].cover);
                chosen.pop_back();
            }
        return found;
    }
    void build_lookup() {
        lookup.assign(12 * board, -1);
        for (size_t i = 0; i < poses.size(); ++i) {
            auto p = poses[i];
            lookup[p.sym * board + location(minus(p.origin, shifts[p.sym]))] = i;
        }
    }
    // Relative placement of b in the reference frame of a. Returns -1 if it
    // is not one of the disjoint neighbors that touches the central shape.
    int relative(Pose a, Pose b) const {
        int inv = group.inverse[a.sym], s = group.product[inv][b.sym];
        Cell t = minus(group.matrices[inv].apply(minus(b.origin, a.origin)), shifts[s]);
        int x = t.first + offset, y = t.second + offset;
        if (x < 0 || x >= stride || y < 0 || y >= stride)
            return -1;
        return lookup[canonical[s] * board + x * stride + y];
    }
    Bits refine(const Bits &old) {
        Bits eligible(words);
        std::vector<int> kept;
        for (size_t i = 0; i < poses.size(); ++i)
            if (contains(old, i)) {
                int rev = relative(poses[i], {0, {0, 0}, 0});
                if (rev < 0)
                    throw std::runtime_error("inverse touching contact absent");
                if (contains(old, rev)) {
                    kept.push_back(i);
                    add(eligible, i);
                }
            }
        for (size_t k = 0; k < kept.size(); ++k)
            for (size_t l = k + 1; l < kept.size(); ++l) {
                int i = kept[k], j = kept[l];
                if (contains(conflict[i], j))
                    continue;
                int ij = relative(poses[i], poses[j]);
                if (ij < 0)
                    continue;
                int ji = relative(poses[j], poses[i]);
                if (ji < 0)
                    throw std::runtime_error("asymmetric touching relation");
                if (!contains(old, ij) || !contains(old, ji)) {
                    add(conflict[i], j);
                    add(conflict[j], i);
                }
            }
        return support(eligible);
    }
    std::array<int, 4> run() {
        std::array<int, 4> counts = {-1, -1, -1, -1};
        for (auto &covers : required)
            if (std::all_of(covers.begin(), covers.end(), [](Word w) { return !w; })) {
                counts[0] = 0;
                return counts;
            }
        build_conflicts();
        Bits eligible(words, ~Word(0));
        if (poses.size() % 64)
            eligible.back() = (Word(1) << (poses.size() % 64)) - 1;
        try {
            for (int d = 0; d < 4; ++d) {
                if (d == 1)
                    build_lookup();
                auto next = d == 0 ? support(eligible) : refine(eligible);
                int n = 0;
                for (Word w : next)
                    n += count(w);
                counts[d] = n;
                if (!n)
                    break;
                eligible = std::move(next);
            }
        } catch (Limit &) {
        } // Unfinished levels stay -1 and are forwarded for retry.
        return counts;
    }
};
#ifndef CONTACT_LIBRARY
int main(int argc, char **argv) {
    if (argc < 2 || argc > 4) {
        std::cerr << "usage: contacts node_limit [shard num_shards]\n";
        return 2;
    }
    uint64_t budget = std::stoull(argv[1]);
    int shard = argc == 4 ? std::stoi(argv[2]) : 0, mod = argc == 4 ? std::stoi(argv[3]) : 1;
    if (mod <= 0 || shard < 0 || shard >= mod)
        throw std::runtime_error("invalid shard selection");
    std::string line;
    while (std::getline(std::cin, line)) {
        std::istringstream in(line);
        int id, x, y;
        if (!(in >> id))
            throw std::runtime_error("missing id");
        if (id % mod != shard)
            continue;
        Shape cells;
        while (in >> x) {
            if (!(in >> y))
                throw std::runtime_error("missing axial coordinate");
            cells.emplace_back(x, y);
        }
        if (cells.empty())
            throw std::runtime_error("empty shape");
        auto c = Search(cells, budget).run();
        std::cout << id;
        for (int n : c)
            std::cout << ' ' << n;
        std::cout << '\n' << std::flush;
    }
}
#endif
