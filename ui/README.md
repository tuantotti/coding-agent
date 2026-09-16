# Coding Agent UI

Giao diện web cho hệ thống multi-agent (`src/`). Kết nối với backend FastAPI qua HTTP + SSE.

## Yêu cầu

- Node.js ≥ 18
- Backend đang chạy tại `http://127.0.0.1:8000` (xem hướng dẫn ở root `README.md`)

## Cài đặt

```bash
cd ui
npm install
```

## Cấu hình môi trường

```bash
cp .env.example .env
```

Mở `.env` và điền:

```env
VITE_API_URL=http://127.0.0.1:8000
```

> Nếu để trống `VITE_API_URL`, Vite sẽ tự proxy `/v1/*` đến `http://127.0.0.1:8000` trong dev mode — cũng chạy được bình thường.

## Chạy development

```bash
npm run dev
# → http://localhost:5173
```

## Build production

```bash
npm run build
# Output: ui/dist/
```

## Cấu trúc thư mục

```
ui/src/
├── App.tsx                    # Root component, layout chính
├── main.tsx                   # Entry point
├── styles.css                 # Global CSS variables & styles
├── components/
│   ├── Sidebar.tsx            # Sidebar lịch sử runs
│   ├── EmptyState.tsx         # Màn hình chờ (orb + chips + agent cards)
│   ├── ChatArea.tsx           # Hiển thị event stream dạng chat bubble
│   ├── MessageBubble.tsx      # Component từng tin nhắn
│   ├── InputCard.tsx          # Ô nhập task + folder browser
│   ├── ApprovalCard.tsx       # Panel approve/reject tool actions
│   └── RunStatusBadge.tsx     # Badge trạng thái run
├── hooks/
│   └── useRunStream.ts        # SSE hook — subscribe /v1/runs/{id}/events
└── services/
    └── api.ts                 # Typed fetch wrapper cho backend API
```

## API backend sử dụng

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `POST` | `/v1/runs` | Tạo run mới |
| `GET` | `/v1/runs/{id}` | Lấy trạng thái run |
| `GET` | `/v1/runs/{id}/events` | SSE stream sự kiện |
| `POST` | `/v1/runs/{id}/resume` | Submit quyết định approve/reject |

## Lưu ý

- `source_folder` phải là **đường dẫn tuyệt đối** (ví dụ `/Users/you/project`, không dùng `.`)
- Nhấn **Browse…** để mở folder picker hoặc gõ thẳng đường dẫn vào ô
- Phím tắt gửi task: `⌘↵` (Mac) hoặc `Ctrl↵` (Windows/Linux)
