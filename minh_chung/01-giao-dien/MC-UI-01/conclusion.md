# MC-UI-01 — Build và phân tách tài nguyên frontend

## Mệnh đề

Frontend vượt qua kiểm tra kiểu, build thành công và tạo các chunk tải độc lập.

## Quan sát

- `npm ci` cài 147 packages và kết thúc thành công.
- `tsc -b && vite build` kết thúc với exit code 0.
- Vite biến đổi 735 modules và hoàn thành build trong 9,96 giây.
- Kết quả có các chunk riêng cho GeoGebra Lab, Function Analyzer, Admin Console, Calculus Simulation, Algebra Solver, KaTeX và Three.js.
- Build cảnh báo `three` lớn hơn 500 kB và `telemetry.ts` vừa được import tĩnh vừa được import động.
- `npm audit` ghi nhận 3 vulnerability: 1 low, 1 moderate, 1 high.

## Kết luận

**Đạt** đối với mệnh đề build, typecheck và phân tách tài nguyên trên workspace local tại thời điểm kiểm tra.

Phạm vi không bao gồm đánh giá hiệu năng tải mạng thực tế. Nội dung đó cần HAR trình duyệt tại MC-PERF-01. Workspace không sạch, vì vậy kết quả gắn với commit nền cùng `WORKSPACE.diff`, không được trình bày như kết quả nguyên trạng của commit `5cac5199...`.