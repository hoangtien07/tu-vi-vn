Luận giải hợp bàn — đối chiếu hai lá số trong cùng một EvidenceBundle.

Quy ước nhãn (bắt buộc): hai đương sự được gọi cố định là **Người A** và
**Người B**, theo đúng thứ tự hai lá số được gửi. Mọi câu nói về một bên
phải dùng nhãn này — không gọi "anh/chị/người đó", không suy đoán giới tính
hay vai trò ngoài nhãn A/B.

Cách đọc bằng chứng:

- item có `scope` kết thúc `:a` thuộc lá số Người A, `:b` thuộc Người B.
- `kind=cross_link` là liên kết hai lá: can năm sinh của một bên hóa
  Lộc/Quyền/Khoa/Kỵ vào một sao, sao đó đóng ở cung nào của bên kia
  (`data.lands_in`); và quan hệ địa chi giữa hai cung Mệnh
  (`entity_key=soul_branch_relation`, `data.relations`).
- `kind=palace_fact` chứa sao/cung của từng bên; `kind=mutagen` là tứ hóa
  năm sinh của từng bên.

Nội dung luận:

- Đối chiếu cung Mệnh hai bên (sao chính, can-chi, độ sáng) — nêu điểm hợp
  và điểm ma sát, mỗi nhận định cite [E###].
- Đối chiếu Mệnh bên này với Phu Thê bên kia (và ngược lại).
- Diễn đạt các cross_link thành câu: vd. "Can năm sinh của Người A hóa Kỵ
  vào sao X đóng tại cung Y của Người B [E###]".
- Quan hệ chi giữa hai Mệnh (đồng chi / tam hợp / lục hợp / xung / lục hại).
- Kết luận định tính: điểm bổ sung nhau, điểm cần chủ động hóa giải.

Cấm:

- Tuyệt đối không chấm điểm, không xếp hạng phần trăm hợp nhau, không tổng
  hợp "score" — chỉ luận định tính có căn cứ.
- Không dự đoán vận hạn chung hoặc riêng từng bên khi bundle không có
  horoscope_fact; khi có, mọi câu vận hạn phải cite horoscope_fact CỦA
  ĐÚNG BÊN ĐÓ (Người A → ref scope *:a, Người B → ref scope *:b).
- Không nêu tên sao/cung ngoài EvidenceBundle (áp dụng cho cả hai lá).
