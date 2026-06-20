from __future__ import annotations

from fastapi import HTTPException, status


ERROR_SUGGESTIONS: dict[str, list[str]] = {
    "INVALID_API_KEY": [
        "Kiểm tra API key trong trang cài đặt provider hoặc biến môi trường backend.",
        "Tạo key mới nếu key cũ hết hạn, bị thu hồi hoặc không có quyền dùng model đã chọn.",
    ],
    "QUOTA_EXCEEDED": [
        "Kiểm tra quota/billing của provider.",
        "Chờ quota hồi lại hoặc đổi sang provider/model khác.",
    ],
    "RATE_LIMITED": [
        "Chờ vài phút rồi thử lại.",
        "Giảm tần suất gọi hoặc đổi model/provider đang ít tải hơn.",
    ],
    "TIMEOUT": [
        "Thử lại sau vài giây hoặc đổi sang model nhẹ hơn.",
        "Kiểm tra base URL, mạng, proxy và trạng thái provider.",
    ],
    "MODEL_NOT_FOUND": [
        "Kiểm tra model ID có đúng provider/model không.",
        "Quét lại danh sách model hoặc chọn model khác trong allowlist.",
    ],
    "PROVIDER_UNAVAILABLE": [
        "Kiểm tra trạng thái provider hoặc base URL.",
        "Thử lại sau hoặc đổi sang provider khác.",
    ],
    "MAINTENANCE_MODE": [
        "Hệ thống đang tạm bảo trì, vui lòng quay lại sau.",
        "Theo dõi thông báo trên trang chủ để biết khi nào hệ thống hoạt động lại.",
    ],
    "PLAN_QUOTA_EXCEEDED": [
        "Chờ sang ngày mới để hạn mức được đặt lại.",
        "Nâng cấp gói hoặc liên hệ admin nếu cần thêm lượt sử dụng.",
    ],
    "INVALID_PROVIDER_RESPONSE": [
        "Provider trả dữ liệu không đúng định dạng. Thử model khác.",
        "Giảm độ phức tạp đề bài nếu lỗi lặp lại.",
    ],
    "OCR_FAILED": [
        "Kiểm tra ảnh có rõ chữ và đúng định dạng không.",
        "Liên hệ admin nếu cần kiểm tra cấu hình OCR hệ thống.",
    ],
    "RENDER_FAILED": [
        "Kiểm tra đề bài và model dựng hình đã chọn.",
        "Thử provider/model khác hoặc viết đề bài rõ hơn.",
    ],
    "SOLVE_FAILED": [
        "Kiểm tra scene đã có đủ điểm, đoạn và đối tượng cần giải.",
        "Thử dựng lại hình hoặc hỏi câu cụ thể hơn.",
    ],
}


def bad_request_from_error(error: Exception, fallback_code: str = "BAD_REQUEST") -> HTTPException:
    detail = classify_error(str(error), fallback_code)
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def api_error(status_code: int, message: str, fallback_code: str = "BAD_REQUEST", suggestions: list[str] | None = None) -> HTTPException:
    detail = classify_error(message, fallback_code, status_code)
    if suggestions is not None:
        detail["suggestions"] = suggestions
    return HTTPException(status_code=status_code, detail=detail)


def classify_error(message: str, fallback_code: str = "BAD_REQUEST", status_code: int | None = None) -> dict[str, object]:
    text = message.lower()
    code = fallback_code.upper()
    if code not in ERROR_SUGGESTIONS:
        if status_code in (401, 403) or any(token in text for token in ["invalid api key", "incorrect api key", "unauthorized", "api key", "forbidden"]):
            code = "INVALID_API_KEY"
        elif "quota" in text or any(token in text for token in ["insufficient", "billing", "credit", "402"]):
            code = "QUOTA_EXCEEDED"
        elif status_code == 429 or "rate limit" in text:
            code = "RATE_LIMITED"
        elif status_code in (408, 504) or any(token in text for token in ["timeout", "timed out", "connecttimeout", "readtimeout"]):
            code = "TIMEOUT"
        elif status_code == 404 or any(token in text for token in ["model not found", "model unavailable", "chưa chọn model"]):
            code = "MODEL_NOT_FOUND"
        elif status_code in (502, 503):
            code = "PROVIDER_UNAVAILABLE"
        elif any(token in text for token in ["json", "schema", "validation", "không hợp lệ"]):
            code = "INVALID_PROVIDER_RESPONSE"

    return {
        "code": code,
        "message": user_message(code, message),
        "suggestions": ERROR_SUGGESTIONS.get(code, ["Kiểm tra dữ liệu đầu vào, cấu hình provider/model và thử lại."]),
        "debug_message": message,
    }


def user_message(code: str, message: str) -> str:
    if code == "INVALID_API_KEY":
        return "API key không hợp lệ, hết hạn hoặc không có quyền dùng model này."
    if code == "QUOTA_EXCEEDED":
        return "Provider đã hết quota hoặc tài khoản chưa đủ billing/credit."
    if code == "RATE_LIMITED":
        return "Provider đang giới hạn tần suất gọi."
    if code == "TIMEOUT":
        return "Provider phản hồi quá lâu."
    if code == "MODEL_NOT_FOUND":
        return "Model đã chọn không tồn tại hoặc không khả dụng."
    if code == "PROVIDER_UNAVAILABLE":
        return "Provider hiện không sẵn sàng."
    if code == "MAINTENANCE_MODE":
        return message or "Hệ thống đang bảo trì."
    if code == "PLAN_QUOTA_EXCEEDED":
        return message or "Bạn đã hết hạn mức sử dụng của gói hiện tại."
    if code == "INVALID_PROVIDER_RESPONSE":
        return "Provider trả dữ liệu không đúng định dạng hệ thống cần."
    return message or "Có lỗi xảy ra."
