# MC-A11Y-01 — Accessibility và hiệu suất trang chủ

## Production trước sửa

- Lighthouse: performance `0.72`, accessibility `0.93`, best practices `0.96`, SEO `0.82`.
- FCP `4297 ms`, LCP `4756 ms`, TBT `17 ms`, CLS `0` trong một lần đo.
- Axe sau `networkidle`: 1 violation `color-contrast`, impact `serious`, ảnh hưởng 10 node footer; tỷ lệ `4.17:1` thấp hơn WCAG AA `4.5:1`.

## Local sau sửa

- Màu chữ footer đổi sang `#475569`.
- `npm run build` thành công.
- Axe trên build local: 0 violation, 38 pass, 3 incomplete.

## Kết luận

**Bản local đạt kiểm tra axe tự động; production chưa đạt trước khi deploy bản sửa.** Lighthouse chỉ là một mẫu lab, không đủ kết luận SLA. Kiểm tra bàn phím, screen reader và 3 mục incomplete vẫn cần thủ công.