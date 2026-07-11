# Implementation Plan: Simulation THPT Library

**Date:** 2026-07-10  
**Status:** Ready for phased execution  
**Source checklist:** [`danh_gia/simulate.md`](../../../danh_gia/simulate.md)  
**Audit baseline:** simulate.md §0 (inventory 4 seed modules, ~1.5/12 P0)

---

## 1. Goal

Nâng Simulation từ **4 module hardcode** thành **thư viện mô phỏng Toán THPT** bám GDPT 2018, với:

1. Cây chương trình (lớp → mạch → chủ đề → mô phỏng)
2. Engine chung (`SimulationSpec` + renderer interface + playbar + checkpoints)
3. Ít nhất **12 mô phỏng P0** đạt publish gate
4. Math verification không phụ thuộc LLM
5. (Sau) teacher mode + AI authoring trên template đã khóa

**Non-goals cho v1 (cắt khỏi “toàn bộ checklist” lần đầu):**

- AI sinh shader/JS tùy ý
- Analytics học tập đầy đủ (chỉ event tối thiểu)
- Ánh xạ chi tiết 3 bộ SGK (để schema, fill data sau)
- Mọi item P1/P2 lớp 10–12

---

## 2. Key decisions

| Quyết định | Lựa chọn | Lý do |
| --- | --- | --- |
| Kiến trúc nội dung | **Template catalog tĩnh (TS/JSON) trước**, DB sau | Ship nhanh, tránh schema churn; migrate sang Postgres khi catalog ổn |
| Math runtime | **Client numerics realtime + optional server SymPy verify** | Slider 60fps; đúng số khi cần “chính xác” |
| Renderer | Adapter: **SVG/Canvas 2D**, **Three 3D**, **reuse MathScene/GeoGebra** khi hợp | Không rewrite 3 stack; interface chung `init/update/reset/destroy` |
| Pedagogy | Mỗi P0: `outcomes` + ≥1 predict + ≥1 checkpoint | Phân biệt demo vs lab học tập |
| AI | **Phase cuối**; AI chỉ chọn template + params theo schema | An toàn, khớp simulate.md §9 |
| Scope ship | 6 phase / ~12 PR stack | Mỗi PR merge được, có DoD |
| Seed migration | Wrap seed hiện tại vào shell mới, **không rewrite toán trước** | Giảm rủi ro regression 3D/Riemann |

---

## 3. Target architecture

```text
User (HS/GV)
  → Simulation Library UI (filter grade/strand/topic)
    → Simulation Runtime Shell
         ├── SimulationSpec (id, grade, params, formulas, steps, checkpoints)
         ├── MathKernel (client eval + optional /api/simulation/verify)
         ├── Renderer adapters (2D | Three | Scene | GeoGebra)
         └── Pedagogy panel (predict → observe → check)
```

### 3.1. SimulationSpec (v1)

```ts
type SimulationSpec = {
  id: string;                 // e.g. "g12.integral.riemann-area"
  version: string;            // semver content
  grade: 10 | 11 | 12;
  strand: "algebra" | "geometry" | "statistics" | "calculus" | "trigonometry" | "probability";
  topicCode: string;          // stable curriculum code
  title: string;
  subtitle?: string;
  kind: "visualization" | "interactive-model" | "process-simulation" | "exploration-lab";
  renderer: "svg2d" | "three" | "mathscene" | "geogebra" | "custom";
  template: string;           // component/template key
  parameters: ParameterDef[];
  formulas: FormulaDef[];
  steps?: StepDef[];          // process timeline
  learningOutcomes: string[];
  prerequisites?: string[];
  checkpoints: CheckpointDef[];
  presets?: PresetDef[];
  verification?: VerificationDef; // server or client rules
  status: "draft" | "published";
  dims: "2d" | "3d" | "hybrid";
};
```

### 3.2. Frontend layout (proposed)

```text
frontend/src/
  simulation/
    catalog/                 # JSON/TS specs + curriculum tree
    runtime/                 # Shell, playbar, param form, checkpoint
    renderers/               # adapters
    math/                    # move/wrap calculus* + trigonometry* utils
    templates/               # one folder per template key
      riemann-area/
      solid-revolution/
      unit-circle-trig/
      ...
    pages/
      SimulationLibraryPage.tsx
      SimulationDetailPage.tsx
```

### 3.3. Backend (from Phase 2b / 5)

```text
backend/app/
  api/routes_simulation.py          # list, get, verify (optional events)
  schemas/simulation.py
  services/simulation/
    catalog.py                      # load published specs
    verify.py                       # SymPy checks for selected templates
  # later: repositories + migrations for overrides, sessions
```

---

## 4. Phased delivery

### Phase 0 — Baseline freeze (0.5–1 ngày)

**Mục tiêu:** khóa hành vi seed trước khi refactor.

| Task | DoD |
| --- | --- |
| Smoke manual 4 module (area, revolution, cross-section, trig) | Ghi checklist pass/fail |
| Unit tests numerics: integrate, riemann, domain, special angles | pytest/vitest tùy stack hiện có (ưu tiên vitest frontend utils) |
| Ghi snapshot công thức hiển thị / giá trị sample preset | Trong PR description |

**PR:** `sim-0-baseline-tests`

---

### Phase 1 — Curriculum tree + library shell (3–5 ngày)

**Mục tiêu:** UI thư viện theo lớp/mạch/chủ đề; catalog tĩnh.

| Task | DoD |
| --- | --- |
| `curriculum_nodes` tĩnh (TS) lớp 10–12, 3 mạch | Render tree + filter |
| `simulation_catalog` đăng ký 4 seed + placeholder P0 | Card: lớp, chủ đề, loại, 2D/3D, status |
| Route `/simulation` → library; `/simulation/:id` → detail | Deep link hoạt động |
| Tab lớp 10/11/12 + search | Khớp simulate.md §7.1 tối thiểu |

**Chưa làm:** DB, AI, quiz.

**PR:** `sim-1-library-catalog`

---

### Phase 2a — Simulation Runtime Engine (5–8 ngày)

**Mục tiêu:** một shell chung thay `CalculusSimulationPage` ad-hoc.

| Task | DoD |
| --- | --- |
| `SimulationShell`: playbar, step, speed, reset, destroy lifecycle | Không rò rỉ rAF/Three khi unmount |
| `ParameterForm` từ `ParameterDef` (slider/number/select/formula) | Validation min/max |
| `FormulaBar` Katex đồng bộ param | Update realtime |
| Renderer interface + mount SVG2D + Three adapters | Seed mount qua adapter |
| Migrate 4 seed → `templates/*` dùng shell | Feature parity với baseline tests |

**PR:** `sim-2a-runtime-engine`  
**Depends:** Phase 0, 1

---

### Phase 2b — Math verification hooks (3–4 ngày)

**Mục tiêu:** đúng toán, tách LLM.

| Task | DoD |
| --- | --- |
| Client kernel giữ numerics | Slider mượt |
| `POST /api/simulation/verify` cho subset (integral value, trig identities sample) | Schema + rate limit auth nếu cần |
| Cảnh báo “xấp xỉ” vs “chính xác” trên UI | Copy rõ |
| Tests backend verify + frontend edge (a≥b, domain hole) | CI xanh |

**PR:** `sim-2b-verify`  
**Depends:** 2a

---

### Phase 3 — Pedagogy kit + nâng seed đạt P0 một phần (4–6 ngày)

**Mục tiêu:** seed không còn “chỉ animation”.

| Task | DoD |
| --- | --- |
| Panel: mục tiêu, tiên quyết, predict, observe, checkpoint | ≥1 checkpoint/template published |
| Nâng Riemann: left/right/mid toggle | So khớp §6.4 một phần |
| Nâng Solid: giữ Ox; document Oy later | §6.5 partial publish |
| Nâng Trig: amplitude/frequency (A, ω) + asymptote markers tan/cot | §5.1 gần P0 |
| Status catalog: `published` cho 2–3 template đủ gate tối thiểu | §13 subset |

**PR:** `sim-3-pedagogy-seed-upgrade`  
**Depends:** 2a (2b optional parallel)

---

### Phase 4 — 12 P0 simulations (theo wave)

Mỗi template: Spec + Template UI + numerics/geometry + ≥1 checkpoint + tests + card catalog.

#### Wave A — hoàn thiện lớp 12 foundation (đã seed) — 1–2 tuần

| ID | Template | Notes |
| --- | --- | --- |
| `g12.integral.riemann-area` | Riemann + area | Promote seed |
| `g12.integral.solid-revolution` | Disk/washer | Promote seed |
| `g12.calculus.derivative-secant` | Cát tuyến → tiếp tuyến | **New** P0 |
| `g12.calc.function-survey` | Đạo hàm + BBT + đồ thị | **New** P0 (có thể lean Analyzer data) |

#### Wave B — lớp 11 P0 — 2–3 tuần

| ID | Template | Notes |
| --- | --- | --- |
| `g11.trig.unit-circle` | Unit circle + graphs | Promote + finish §5.1 |
| `g11.trig.equations` | sin/cos/tan = m | **New** |
| `g11.calc.limits-continuity` | ε-table + one-sided | **New** |
| `g11.geom.space-relations` | Parallel/perp 3D | **New** (reuse Three/MathScene) |
| `g11.prob.tree` | Probability tree | **New** |

> Note: checklist §14 lớp 11 có 4 slot; `trig.equations` có thể gộp vào unit-circle v1.1 nếu thiếu bandwidth — **ưu tiên 4 slot §14 trước**.

#### Wave C — lớp 10 P0 — 2–3 tuần

| ID | Template |
| --- | --- |
| `g10.algebra.linear-ineq-region` | Miền BPT hai ẩn |
| `g10.algebra.quadratic` | Parabol + discriminants + dấu |
| `g10.geom.triangle-laws` | Sin/cos laws dynamic triangle |
| `g10.geom.vectors-2d` | Cộng/trừ, chấm, góc |

#### Wave D — lớp 12 remaining P0 — 1–2 tuần

| ID | Template |
| --- | --- |
| `g12.geom.space-coords` | Oxyz line/plane/sphere intro |
| `g12.prob.bayes` | Conditional + Bayes visual |

**PRs:** `sim-4a-…` … `sim-4d-…` (1–2 template/PR để review được)

**Definition of Done mỗi P0:**

- [ ] Có trong catalog + filter đúng lớp/chủ đề
- [ ] Spec versioned
- [ ] Learning outcomes + checkpoint
- [ ] Math edge cases tested
- [ ] Responsive desktop; usable tablet
- [ ] Không crash khi param biên
- [ ] `status: published` sau review toán

---

### Phase 5 — Teacher mode (1–2 tuần)

| Task | DoD |
| --- | --- |
| Fullscreen + presentation CSS | Ẩn chrome thừa |
| Shareable URL state (params query/hash) | Mở lại đúng preset |
| Lock parameters toggle | GV khóa khi trình chiếu |
| Export PNG of stage (html2canvas hoặc canvas) | 1 click |
| (Optional) lesson playlist local | JSON list id |

**PR:** `sim-5-teacher-mode`  
**Depends:** Phase 4 Wave A tối thiểu

---

### Phase 6 — Persistence + light analytics (1 tuần)

| Task | DoD |
| --- | --- |
| Migration: `simulation_templates` / versions **hoặc** sync catalog → DB | Admin list |
| Events: open, reset, checkpoint_submit (anonymous session ok) | Không PII thừa |
| Favorites client (localStorage) rồi user-linked nếu auth | §7.1 favorite |

**PR:** `sim-6-persistence-events`

---

### Phase 7 — AI authoring (sau template ổn) (2+ tuần)

| Task | DoD |
| --- | --- |
| Intent classifier: grade/topic/template | Chỉ map template whitelist |
| Param extraction + JSON schema validate | Reject arbitrary code |
| Generate predict/checkpoint text; **answer check via MathKernel** | Không tin LLM số |
| Teacher preview + edit + publish | Human in the loop |

**PR:** `sim-7-ai-authoring`  
**Depends:** Phase 2 + ≥6 published templates

---

## 5. PR stack (ordered)

```text
sim-0  Baseline tests
  └── sim-1  Library + curriculum catalog
        └── sim-2a Runtime engine + migrate seeds
              ├── sim-2b Verify API
              └── sim-3  Pedagogy + seed P0 polish
                    ├── sim-4a g12 promote + derivative
                    ├── sim-4b g11 P0
                    ├── sim-4c g10 P0
                    ├── sim-4d g12 space + bayes
                    └── sim-5 Teacher mode
                          └── sim-6 Persistence
                                └── sim-7 AI authoring
```

Cross-section volume: giữ trong catalog `status: draft` hoặc `published` bonus — **không chặn 12 P0**.

---

## 6. Effort estimate (rough)

| Phase | Effort (eng-days) | Cumulative |
| --- | --- | --- |
| 0 | 1 | 1 |
| 1 | 4 | 5 |
| 2a | 7 | 12 |
| 2b | 4 | 16 |
| 3 | 5 | 21 |
| 4 (all P0) | 30–45 | 51–66 |
| 5 | 7 | 58–73 |
| 6 | 5 | 63–78 |
| 7 | 10–15 | 73–93 |

≈ **3–5 tháng** 1 full-stack dev (hoặc ~1.5–2 tháng 2 dev song song wave 4).

**MVP có giá trị sản phẩm (khuyến nghị ship sớm):** Phase 0→3 + Wave A (+ unit-circle published) ≈ **4–6 tuần**.

---

## 7. Testing strategy

| Layer | What |
| --- | --- |
| Unit | Expression compile, integrate, riemann modes, trig safe tan/cot, param clamps |
| Component | Shell step transitions; checkpoint correct/incorrect |
| Visual smoke | Playwright optional: open each published id, no console error |
| Math golden | Table of (params → expected) for each P0; server verify when available |
| Perf | Unmount no leak; 3D ≤ target FPS on mid laptop |

---

## 8. Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| Scope explosion checklist | Hard cut P1/P2; only 12 P0 in v1 |
| 3D migration breaks Solid | Phase 0 golden + adapter wrap without math rewrite |
| Curriculum coding disputes | Stable `topicCode` internal; textbook mapping later |
| Wrong math in pedagogy | Publish gate + golden tests; no LLM for numbers |
| Mobile 3D poor | Disable heavy 3D auto-rotate on small screens; static fallback |

---

## 9. Immediate next actions (start now)

1. Merge/update `danh_gia/simulate.md` §0 (done in same effort).
2. Open **sim-0**: extract pure functions tests for `calculusNumerics` + `trigonometryNumerics`.
3. Scaffold `frontend/src/simulation/catalog/` with curriculum stub + 4 seed entries.
4. Do **not** start new P0 topics before Runtime Shell (2a).

---

## 10. Success criteria (v1 first release)

Khớp rút gọn simulate.md §16:

- [x] Audit hiện trạng documented  
- [ ] Cấu trúc lớp 10–11–12 trên UI  
- [ ] Filter mạch + chủ đề  
- [ ] ≥12 P0 published (hoặc MVP: ≥5 published gồm 2 seed + 3 new)  
- [ ] Mỗi published: outcomes + checkpoint  
- [ ] Math verification path (client + optional server)  
- [ ] Responsive library + detail  
- [ ] Teacher fullscreen + share URL  
- [ ] CI tests cho numerics + 1 e2e smoke  

---

## 11. Open questions (cần product confirm khi vào Phase 1+)

1. **MVP cut:** ship thư viện sau Phase 3 (4–5 sim) hay chặn release đến đủ 12 P0?
2. **GeoGebra:** embed như renderer template hay giữ Lab tách hẳn?
3. **Auth:** simulation public không login, checkpoint lưu user chỉ khi đã login?
4. **Ngôn ngữ UI:** chỉ VI hay VI+EN keys trong Spec?

**Quyết định đã chốt (2026-07-10):**
- Làm **đến hết Phase 3** (MVP engine + library + pedagogy + seed polish).
- **Không** multi-user / chia sẻ / favorites server.
- **VI only**, sim **public**, **GeoGebra Lab tách**.
- Chỉ đụng code thuần Simulation; không phụ thuộc Render/Algebra/Analyzer.

---

## PR Plan (summary table)

| PR | Title | Depends | Main paths |
| --- | --- | --- | --- |
| sim-0 | Baseline numerics tests for simulation seeds | — | `frontend/src/utils/*`, tests |
| sim-1 | Simulation library + curriculum catalog | sim-0 | `frontend/src/simulation/catalog`, pages, App routes |
| sim-2a | Runtime shell + migrate 4 seeds | sim-1 | `simulation/runtime`, `templates/*` |
| sim-2b | Simulation verify API | sim-2a | `backend/app/api/routes_simulation.py`, services |
| sim-3 | Pedagogy kit + seed P0 polish | sim-2a | runtime pedagogy, seed templates |
| sim-4a–d | P0 content waves | sim-3 | templates + catalog + tests |
| sim-5 | Teacher mode | sim-4a | shell presentation, URL state |
| sim-6 | Persistence + events | sim-5 | migrations, repos |
| sim-7 | AI authoring on templates | sim-6 + enough templates | AI routes constrained to schema |
