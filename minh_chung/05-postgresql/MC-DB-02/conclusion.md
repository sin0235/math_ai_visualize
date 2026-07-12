# MC-DB-02 — Migration PostgreSQL

Hai lần chạy migration trên PostgreSQL local đều kết thúc với 11/11 migration, không drift, không migration thừa/thiếu và không duplicate prefix. Schema quan sát có 312 CHECK, 41 FOREIGN KEY, 41 PRIMARY KEY, 10 UNIQUE constraint.

## Kết luận

**Đạt cho migration local và idempotence.** Không suy diễn rằng production đã chạy cùng migration; production cần truy vấn bảng migration bằng quyền đọc để xác nhận riêng.