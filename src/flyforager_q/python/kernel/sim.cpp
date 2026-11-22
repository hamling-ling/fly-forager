// Decision kernel of the foraging robot: extracted 687-neuron feeding
// subcircuit (FlyWire v783), hunger/satiety states from Experiment D/E.
//
// Mirrors numpy_sub.py semantics exactly (which mirrors Brian2 model.py):
//   dv/dt = (v0 - v + g)/20ms, dg/dt = -g/5ms, exact per-step solution,
//   dt = 0.1 ms; threshold -45 mV; reset v=-52, g=0; refractory 2.2 ms
//   (frozen ODE; synaptic jumps landing during refractory are DISCARDED);
//   synaptic delay 1.8 ms; Poisson input on sugar GRNs: v += 68.75 mV.
//
// State (Experiment D): the effective input rate is nominal x k_p
// (peripheral gain). Outputs of predicted-GABAergic neurons (gaba.bin,
// sugar GRN outputs excluded) are scaled by g_gaba (brake tone).
//   base:     k_p 1.00, g_gaba 1.0
//   hungry:   k_p 1.50, g_gaba 0.7   (set H3)
//   satiated: k_p 0.67, g_gaba 1.3   (set S3)
//
// Usage: sim <nominal_rate_hz> <n_trials> <k_p> <g_gaba> [seed]
// Reads indptr.bin / post.bin / w_base.bin / gaba.bin / sugar.bin from
// the current directory. The last line is machine-readable:
//   result mn9_mean <mean> mn9_counts <c0,c1,...>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <vector>

static const double V0 = -52.0, V_TH = -45.0;
static const double DT = 0.1;                 // ms
static const int N_STEPS = 10000;             // 1000 ms
static const int RFC_STEPS = 22;              // 2.2 ms
static const int DELAY_STEPS = 18;            // 1.8 ms
static const double POI_JUMP = 68.75;         // mV
static const double E_T = std::exp(-DT / 20.0);
static const double E_TAU = std::exp(-DT / 5.0);

template <typename T>
static std::vector<T> load(const char* path) {
    std::ifstream f(path, std::ios::binary | std::ios::ate);
    if (!f) { std::fprintf(stderr, "cannot open %s\n", path); std::exit(1); }
    std::streamsize bytes = f.tellg();
    f.seekg(0);
    std::vector<T> v(bytes / sizeof(T));
    f.read(reinterpret_cast<char*>(v.data()), bytes);
    return v;
}

// splitmix64: small fast RNG, good enough for Bernoulli draws
struct Rng {
    uint64_t s;
    explicit Rng(uint64_t seed) : s(seed) {}
    uint64_t next() {
        uint64_t z = (s += 0x9E3779B97F4A7C15ull);
        z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
        z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
        return z ^ (z >> 31);
    }
    double uniform() { return (next() >> 11) * (1.0 / 9007199254740992.0); }
};

int main(int argc, char** argv) {
    double nominal = argc > 1 ? std::atof(argv[1]) : 60.0;
    int n_trials = argc > 2 ? std::atoi(argv[2]) : 3;
    double k_p = argc > 3 ? std::atof(argv[3]) : 1.0;
    double g_gaba = argc > 4 ? std::atof(argv[4]) : 1.0;
    uint64_t seed0 = argc > 5 ? std::strtoull(argv[5], nullptr, 10) : 1000;

    auto indptr = load<int64_t>("indptr.bin");
    auto post = load<int32_t>("post.bin");
    auto w = load<double>("w_base.bin");
    auto gaba = load<uint8_t>("gaba.bin");
    auto sugar = load<int32_t>("sugar.bin");
    const int n = (int)indptr.size() - 1;
    const int mn9 = 680;  // from meta.txt (flyid 720575940660219265)
    std::vector<char> is_sugar(n, 0);
    for (int32_t s : sugar) is_sugar[s] = 1;

    if (gaba.size() == w.size() && g_gaba != 1.0)
        for (size_t e = 0; e < w.size(); e++)
            if (gaba[e]) w[e] *= g_gaba;

    const double rate = nominal * k_p;
    const double p = rate * DT / 1000.0;
    std::vector<double> v(n), g(n);
    std::vector<int> refr(n);
    std::vector<std::pair<int32_t, double>> ring[DELAY_STEPS + 1];
    std::vector<int> spikes;
    spikes.reserve(1024);

    double wall_sum = 0.0;
    long mn9_sum = 0;
    std::vector<long> counts;
    for (int tr = 0; tr < n_trials; tr++) {
        auto t0 = std::chrono::steady_clock::now();
        std::fill(v.begin(), v.end(), V0);
        std::fill(g.begin(), g.end(), 0.0);
        std::fill(refr.begin(), refr.end(), 0);
        for (auto& slot : ring) slot.clear();
        Rng rng(seed0 + tr);
        long mn9_count = 0, total = 0;
        for (int step = 0; step < N_STEPS; step++) {
            // 1) exact ODE update, non-refractory only
            for (int i = 0; i < n; i++) {
                if (refr[i] <= step) {
                    double ga = g[i];
                    g[i] = ga * E_TAU;
                    v[i] = V0 + (v[i] - V0 + ga / 3.0) * E_T - (ga / 3.0) * E_TAU;
                }
            }
            // 2) threshold, reset, schedule deliveries
            spikes.clear();
            for (int i = 0; i < n; i++) {
                if (refr[i] <= step && v[i] > V_TH) spikes.push_back(i);
            }
            if (!spikes.empty()) {
                total += (long)spikes.size();
                auto& slot = ring[(step + DELAY_STEPS) % (DELAY_STEPS + 1)];
                for (int s : spikes) {
                    if (s == mn9) mn9_count++;
                    v[s] = V0;
                    g[s] = 0.0;
                    refr[s] = is_sugar[s] ? step : step + RFC_STEPS;
                    for (int64_t e = indptr[s]; e < indptr[s + 1]; e++)
                        slot.emplace_back(post[e], w[e]);
                }
            }
            // 3) deliveries; jumps to refractory neurons are discarded
            {
                auto& slot = ring[step % (DELAY_STEPS + 1)];
                for (auto& pw : slot)
                    if (refr[pw.first] <= step) g[pw.first] += pw.second;
                slot.clear();
            }
            // 4) Poisson jumps on sugar neurons
            if (p > 0.0)
                for (int32_t s : sugar)
                    if (rng.uniform() < p) v[s] += POI_JUMP;
        }
        double wall = std::chrono::duration<double>(
                          std::chrono::steady_clock::now() - t0).count();
        wall_sum += wall;
        mn9_sum += mn9_count;
        counts.push_back(mn9_count);
        std::printf("trial %d: MN9 %ld, total %ld, wall %.4f s\n",
                    tr, mn9_count, total, wall);
    }
    double mean = n_trials > 0 ? (double)mn9_sum / n_trials : 0.0;
    std::printf("mean wall %.4f s over %d trials (nominal %.0f Hz, "
                "k_p %.2f, g_gaba %.2f, n=%d)\n",
                wall_sum / n_trials, n_trials, nominal, k_p, g_gaba, n);
    std::printf("result mn9_mean %.2f mn9_counts ", mean);
    for (size_t i = 0; i < counts.size(); i++)
        std::printf("%s%ld", i ? "," : "", counts[i]);
    std::printf("\n");
    return 0;
}
