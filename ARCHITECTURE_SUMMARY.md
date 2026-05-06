# HÌNH TOÁN AI - COMPREHENSIVE ARCHITECTURE MAP

## PROJECT OVERVIEW
Vietnamese math education platform (Grades 10-12) for geometric visualization
- Backend: 8,330 lines Python (FastAPI)
- Frontend: 8,552 lines TypeScript (React 18 + Vite)

## PART 1: AI/ML CAPABILITIES BUILT-IN

### 1.1 Multi-Provider AI Infrastructure
✓ OpenRouter (primary: text + vision models)
✓ NVIDIA NIM (cloud inference)  
✓ Ollama (local LLM)
✓ 9router (local model router)
✓ Mock (fallback testing)
✓ Auto-fallback chain when provider fails

Key Files:
- backend/app/services/openrouter_client.py (9.2KB)
- backend/app/services/nvidia_client.py (9.3KB)
- backend/app/services/ollama_client.py (10.3KB)
- backend/app/services/router9_client.py (11.1KB)

### 1.2 OCR Service (Vision-Based Text Extraction)
✓ Supported formats: PNG, JPEG, WebP, GIF (base64 data URLs)
✓ Max size: 8MB
✓ Provider fallback: Router9 → OpenRouter → NVIDIA

File: backend/app/services/ocr.py (6.6KB)

### 1.3 Scene Extraction (AI Problem Understanding)
✓ Two-stage processing (reasoning + extraction)
✓ Outputs: MathScene with objects, relations, annotations
✓ Supports: 2D geometry, 3D geometry, function graphs

Files:
- backend/app/services/extractor.py (24.5KB)
- backend/app/services/ai_prompt.py (31.4KB)

### 1.4 Function Analysis Service (SymPy-Based) ← KHẢO SÁT
✓ Derivative, critical points, asymptotes, intercepts
✓ Vietnamese variation table (bảng biến thiên)
✓ Supports: Vietnamese notation (x^2, sqrt, exp, etc.)

File: backend/app/services/function_analyzer.py (10.6KB)

### 1.5 Geometry Solver (Step-by-Step)
✓ Step-by-step solutions for geometry problems
✓ Uses LLM with reasoning prompts

File: backend/app/services/solver_service.py (20.8KB)

### 1.6 Geometry Engine (Normalization)
✓ Auto-compute intersections, generate annotations
✓ Segment intersection, coordinate generation

File: backend/app/services/geometry_engine.py (23.1KB)

## PART 2: VISUALIZATION CAPABILITIES

### 2.1 GeoGebra Renderer (2D & 3D)
✓ Converts MathScene JSON → GeoGebra commands
✓ Supports: Points, lines, circles, 3D objects, functions
✓ Interactive: dragging, zoom, rotate, export

Backend: backend/app/renderers/geogebra_commands.py (11.5KB)
Frontend: frontend/src/components/GeoGebraView.tsx

### 2.2 Three.js Renderer (3D Geometry)
✓ Custom 3D rendering, interactive controls
Frontend: frontend/src/components/ThreeView.tsx

### 2.3 Math Rendering (LaTeX/KaTeX)
✓ KaTeX (0.16.45) for rendering LaTeX formulas
Frontend: frontend/src/components/KatexSpan.tsx

## PART 3: CURRENT STATE OF KHẢO SÁT HÀM SỐ

### Backend Endpoint: POST /api/analyze
Location: backend/app/api/routes_solve.py (lines 118-160)
Request: {"expression": "x^3 - 3*x + 2"}
Response: AnalyzeResponse with derivative, critical_points, asymptotes, etc.

### Frontend Component: FunctionAnalyzerPanel
Location: frontend/src/components/FunctionAnalyzerPanel.tsx (348 lines)
Features:
- Expression input with example chips
- Results: derivative, variation table, critical points, asymptotes, intercepts
- Vietnamese-style BBT with arrows (↗/↘)
- Error handling and warnings

## PART 4: ALL BACKEND SERVICES (Summary)

Service                    Size      Purpose
================================================================
extractor.py              24.5KB    Scene extraction from text
ai_prompt.py              31.4KB    System prompts for LLM
geometry_engine.py        23.1KB    Scene normalization
solver_service.py         20.8KB    Step-by-step solver
router9_client.py         11.1KB    9router API client
geogebra_commands.py      11.5KB    GeoGebra command gen
solid_presets.py          12.6KB    Pre-built 3D geometries
openrouter_client.py      9.2KB     OpenRouter API client
nvidia_client.py          9.3KB     NVIDIA NIM API client
ollama_client.py          10.3KB    Ollama client
function_analyzer.py      10.6KB    SymPy analysis ← KHẢO SÁT
ocr.py                    6.6KB     OCR orchestration

## PART 5: ALL BACKEND API ENDPOINTS

/api/render                POST    Extract scene from problem
/api/ocr                   POST    Extract text from image
/api/analyze               POST    Function analysis ← KEY
/api/solve                 POST    Geometry solver
/api/health                GET     Health check
/api/settings/defaults     GET     Provider defaults
/api/ai/models/scan        GET     Scan 9router models
/api/history/render        GET     Render history
/api/auth/*                POST/GET Login, register, OAuth
/api/user/settings         GET/PUT User preferences
/api/admin/*               GET/POST Admin console

## PART 6: MAXIMIZING KHẢO SÁT HÀM SỐ

### Current Capabilities ✓
✓ Derivative, critical points, asymptotes, intercepts
✓ Vietnamese variation table
✓ LaTeX formula rendering
✓ Error handling, warnings

### Priority 1: Visual Graph Rendering
Add function graph visualization in GeoGebra or Plotly
- Generate points from f(x)
- Highlight critical points, asymptotes
- Interactive domain adjustment
- Export as image

### Priority 2: Enhanced Analysis
- Concavity analysis (inflection points via f''(x))
- Domain & range calculation
- Partial fraction decomposition
- Even/odd function detection

### Priority 3: Step-by-Step Explanations
- Generate explanation steps for each calculation
- Use existing solver_service as template

### Priority 4: Function Comparison
- Analyze multiple functions
- Side-by-side comparison
- POST /api/analyze/batch endpoint

### Priority 5: Database Persistence
- Store favorite functions
- Save analysis history
- User collections

### Priority 6: Export Capabilities
- Export to PDF
- Export graph as image
- Export as LaTeX

## PART 7: QUICK START - ADD GRAPH VISUALIZATION

Backend:
1. Create backend/app/services/function_grapher.py
2. Function: generate_function_graph_scene(analysis: dict) → MathScene
3. Update routes_solve.py to call it

Frontend:
1. In FunctionAnalyzerPanel.tsx
2. Add: {result?.graph_scene && <GeoGebraView scene={result.graph_scene} />}

## PART 8: KEY FILE REFERENCES

Backend (for KHẢO SÁT):
- backend/app/api/routes_solve.py (lines 118-160)
- backend/app/services/function_analyzer.py
- backend/app/schemas/scene.py
- backend/app/renderers/geogebra_commands.py (for future graphs)

Frontend (for KHẢO SÁT):
- frontend/src/components/FunctionAnalyzerPanel.tsx (348 lines)
- frontend/src/components/KatexSpan.tsx
- frontend/src/components/GeoGebraView.tsx
- frontend/src/api/client.ts (analyzeFunction at line 518)
- frontend/src/styles.css (fa2-* classes)

## DEPENDENCIES

Backend: FastAPI, pydantic, SymPy, httpx, aiosqlite, bcrypt, resend
Frontend: React 18, TypeScript, KaTeX, Three.js, Vite

## DEPLOYMENT

Local: Backend at localhost:8000, Frontend at localhost:5173
Production: Vercel (frontend) with backend URL configuration

## SUMMARY

✅ 8,330 lines Python backend with multi-provider AI
✅ 8,552 lines TypeScript frontend with interactive visualization
✅ Active KHẢO SÁT feature using SymPy
✅ Modular, extensible architecture
✅ Production-ready with auth, history, admin console

Can be maximized by adding:
1. Visual graph rendering (HIGH)
2. Concavity analysis, domain/range (HIGH)
3. Step-by-step explanations
4. Batch comparison tool
5. Export capabilities
