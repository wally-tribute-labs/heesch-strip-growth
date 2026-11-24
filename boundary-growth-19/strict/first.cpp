// Exact cover of the first halo. Every chosen tile touches the center in an edge.
// Every terminal packing is connected, so Euler characteristic 1 means no holes.
#include <algorithm>
#include <array>
#include <bit>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <limits>
#include <set>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

using Word = std::uint64_t;
using Cell = std::pair<int,int>;
using Shape = std::vector<Cell>;
using Matrix = std::array<int,4>;
constexpr Matrix orientations[] = {
    {1,0,0,1},{0,-1,1,1},{-1,-1,1,0},{-1,0,0,-1},{0,1,-1,-1},{1,1,-1,0},
    {0,1,1,0},{-1,0,1,1},{-1,-1,0,1},{0,-1,-1,0},{1,0,-1,-1},{1,1,0,-1}
};
constexpr Cell neighbors[] = {{0,-1},{0,1},{1,0},{-1,0},{1,-1},{-1,1}};
constexpr int offset = 21; // Size <=19 gives diameter <=18; one touching copy reaches at most 19 cells outward.
constexpr int side = 64;
using Board = std::array<Word,side>;
int index(int z) {
    assert(z+offset > 0 && z+offset < side-1);
    return z+offset;
}

struct Pose {
    int sym, x, y;
    Word halo;
    std::vector<std::pair<int,Word>> rows;
};

struct Search {
    Board occupied{};
    std::vector<Pose> poses;
    std::vector<std::vector<int>> owners;
    std::vector<int> order, selected;
    Word needed{};
    int y_low=side,y_high=0;
    long long nodes=0, completed=0;

    explicit Search(const Shape& tile) {
        std::set<Cell> center(tile.begin(),tile.end()), halo;
        for(auto [x,y]:center) {
            occupied[index(y)] |= Word(1)<<index(x);
            for(auto [dx,dy]:neighbors) if(!center.count({x+dx,y+dy})) halo.insert({x+dx,y+dy});
        }
        assert(halo.size()<64);
        needed=(Word(1)<<halo.size())-1;
        Shape boundary(halo.begin(),halo.end());
        owners.resize(halo.size());
        std::set<Shape> aspects;
        for(int s=0;s<12;s++) {
            auto [a,b,d,e]=orientations[s];
            Shape image;
            for(auto [x,y]:center) image.push_back({a*x+b*y,d*x+e*y});
            std::sort(image.begin(),image.end());
            // Keep raw affine coordinates in output, but deduplicate translated aspects.
            Shape normalized;
            for(auto [x,y]:image) normalized.emplace_back(x-image.front().first,y-image.front().second);
            if(!aspects.insert(normalized).second) continue;
            std::set<Cell> shifts;
            for(auto [x,y]:halo) for(auto [u,v]:image) shifts.insert({x-u,y-v});
            for(auto [dx,dy]:shifts) {
                Board rows{};
                bool fits=true;
                int lo=side, hi=0;
                for(auto [x,y]:image) {
                    int j=index(y+dy);
                    Word bit=Word(1)<<index(x+dx);
                    if(occupied[j]&bit){fits=false;break;}
                    rows[j]|=bit;
                    lo=std::min(lo,j); hi=std::max(hi,j);
                }
                if(!fits) continue;
                Pose p{s,dx,dy,0,{}};
                for(int j=lo;j<=hi;j++) if(rows[j]) p.rows.emplace_back(j,rows[j]);
                for(unsigned j=0;j<boundary.size();j++) {
                    auto [x,y]=boundary[j];
                    if(rows[index(y)] & (Word(1)<<index(x))) {
                        p.halo|=Word(1)<<j;
                        owners[j].push_back(poses.size());
                    }
                }
                assert(p.halo);
                y_low=std::min(y_low,lo); y_high=std::max(y_high,hi);
                poses.push_back(std::move(p));
            }
        }
        for(auto [x,y]:center){ y_low=std::min(y_low,index(y)); y_high=std::max(y_high,index(y)); }
        for(unsigned j=0;j<owners.size();j++) order.push_back(j);
        std::sort(order.begin(),order.end(),[&](int i,int j){return owners[i].size()<owners[j].size();});
    }
    bool free(int i) const {
        for(auto [j,b]:poses[i].rows) if(occupied[j]&b) return false;
        return true;
    }
    void toggle(int i) { for(auto [j,b]:poses[i].rows) occupied[j]^=b; }

    bool hole_free() const {
        // Inclusion/exclusion for the nerve of closed hexagonal cells. Adjacent pairs
        // intersect in edges, triple-wise adjacent sets meet in single vertices, and
        // nothing higher intersects. Hexes at (x,y) meet (x,y+1) and (x-1,y+1).
        int chi=0;
        for(int y=y_low;y<=y_high;y++) {
            Word r=occupied[y], up=occupied[y+1];
            chi+=std::popcount(r);
            chi-=std::popcount(r&(r>>1))+std::popcount(r&up)+std::popcount(r&(up<<1));
            chi+=std::popcount(r&(r>>1)&up)+std::popcount(r&up&(up<<1));
        }
        if(chi>1) throw std::runtime_error("disconnected first ring");
        return chi==1;
    }

    bool find(Word remaining) {
        nodes++;
        if(!remaining){completed++; return hole_free();}
        int best=-1, count=std::numeric_limits<int>::max();
        for(int j:order) if(remaining & (Word(1)<<j)) {
            int choices=0;
            for(int i:owners[j]){
                if(free(i) && ++choices>=count) break;
            }
            if(!choices) return false;
            if(choices<count){best=j;count=choices;}
        }
        assert(best>=0);
        for(int i:owners[best]) if(free(i)) {
            selected.push_back(i);
            toggle(i);
            if(find(remaining & ~poses[i].halo)) return true;
            toggle(i);
            selected.pop_back();
        }
        return false;
    }
};

int main(int argc,char** argv) {
    // Shards determine scheduling only.
    int shard=argc>1 ? std::stoi(argv[1]):0, nshards=argc>2?std::stoi(argv[2]):1;
    std::string line;
    std::ios_base::sync_with_stdio(false);
    while(std::getline(std::cin,line)){
        std::stringstream parser(line);
        int id,x,y; parser>>id;
        if(id%nshards!=shard) continue;
        Shape tile;
        while(parser>>x>>y)tile.push_back({x,y});
        if(tile.empty()||tile.size()>19) throw std::runtime_error("expected 1-19 hexes");
        Search search(tile);
        bool exists=search.find(search.needed);
        std::cout<<id<<'\t'<<int(exists)<<'\t'<<search.nodes<<'\t'<<search.completed;
        for(int i:search.selected){
            auto &p=search.poses[i]; std::cout<<'\t'<<p.sym<<','<<p.x<<','<<p.y;
        }
        std::cout<<'\n';
    }
}
