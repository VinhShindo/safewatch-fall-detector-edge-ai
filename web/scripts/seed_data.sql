-- =====================================================================
--  SEED DATA ONLY (bảng đã tồn tại)
--  Chạy trong 1 transaction để rollback nếu có lỗi
-- =====================================================================
BEGIN;

-- ---------------------------------------------------------------------
-- 1. FACILITIES  (managerStaffId để NULL, update sau khi có staff)
-- ---------------------------------------------------------------------
INSERT INTO "facilities" ("id","data") VALUES
('FAC-001', '{"id":"FAC-001","name":"Cơ sở Bình An","address":"12 Nguyễn Trãi, Hà Nội","managerStaffId":null,"phone":"0241234567"}'::jsonb),
('FAC-002', '{"id":"FAC-002","name":"Cơ sở An Khang","address":"45 Lê Lợi, TP. Hồ Chí Minh","managerStaffId":null,"phone":"0287654321"}'::jsonb);

-- ---------------------------------------------------------------------
-- 2. ROOMS
-- ---------------------------------------------------------------------
INSERT INTO "rooms" ("id","data") VALUES
('ROOM-001', '{"id":"ROOM-001","facilityId":"FAC-001","name":"Phòng 101","floor":1}'::jsonb),
('ROOM-002', '{"id":"ROOM-002","facilityId":"FAC-001","name":"Phòng 102","floor":1}'::jsonb),
('ROOM-003', '{"id":"ROOM-003","facilityId":"FAC-002","name":"Phòng 201","floor":2}'::jsonb);

-- ---------------------------------------------------------------------
-- 3. STAFF
-- ---------------------------------------------------------------------
INSERT INTO "staff" ("id","data") VALUES
('STAFF-001', '{"id":"STAFF-001","fullName":"Nguyễn Văn Nam","role":"Điều dưỡng","facilityId":"FAC-001","phone":"0901234567","email":"nam@gmail.com","shiftStart":"07:00","shiftEnd":"19:00"}'::jsonb),
('STAFF-002', '{"id":"STAFF-002","fullName":"Trần Thị Hoa","role":"Quản lý","facilityId":"FAC-001","phone":"0902345678","email":"hoa@gmail.com","shiftStart":"08:00","shiftEnd":"17:00"}'::jsonb),
('STAFF-003', '{"id":"STAFF-003","fullName":"Lê Minh Tuấn","role":"Điều dưỡng","facilityId":"FAC-002","phone":"0903456789","email":"tuan@gmail.com","shiftStart":"07:00","shiftEnd":"19:00"}'::jsonb);

-- Gán trưởng cơ sở (sau khi staff đã tồn tại)
UPDATE "facilities" SET "data" = jsonb_set("data", '{managerStaffId}', '"STAFF-002"'::jsonb) WHERE "id" = 'FAC-001';
UPDATE "facilities" SET "data" = jsonb_set("data", '{managerStaffId}', '"STAFF-003"'::jsonb) WHERE "id" = 'FAC-002';

-- ---------------------------------------------------------------------
-- 4. RESIDENTS  (deviceId để NULL, update sau khi có devices)
-- ---------------------------------------------------------------------
INSERT INTO "residents" ("id","data")
VALUES
('USR-001', '{"id":"USR-001","fullName":"Trần Văn Minh","gender":"Nam","birthYear":1948,"facilityId":"FAC-001","roomId":"ROOM-001","staffId":"STAFF-001","deviceId":null,"isMonitored":true,"contact":{"name":"Trần Thị Lan","relation":"Con gái","phone":"0909876543","email":"lan@gmail.com"}}'::jsonb),
('USR-002', '{"id":"USR-002","fullName":"Phạm Thị Lan","gender":"Nữ","birthYear":1952,"facilityId":"FAC-001","roomId":"ROOM-002","staffId":"STAFF-001","deviceId":null,"isMonitored":true,"contact":{"name":"Phạm Văn Hùng","relation":"Con trai","phone":"0912345678","email":"hung@gmail.com"}}'::jsonb),
('USR-003', '{"id":"USR-003","fullName":"Hoàng Văn Đức","gender":"Nam","birthYear":1945,"facilityId":"FAC-002","roomId":"ROOM-003","staffId":"STAFF-003","deviceId":null,"isMonitored":true,"contact":{"name":"Hoàng Thị Mai","relation":"Con gái","phone":"0923456789","email":"mai@gmail.com"}}'::jsonb);

-- ---------------------------------------------------------------------
-- 5. DEVICES
-- ---------------------------------------------------------------------
INSERT INTO "devices" ("id","data")
VALUES
('SW-0001', '{"id":"SW-0001","userId":"USR-001","facilityId":"FAC-001","roomId":"ROOM-001","status":"Active","battery":86,"heartRate":72,"fallStatus":"NoFall","fallProbability":0.01,"connectionStatus":"Good","rssi":-60,"lastUpdatedUtc":"2026-09-21T08:30:00Z","lastSyncUtc":"2026-09-21T08:30:00Z","firmwareVersion":"v1.2.4"}'::jsonb),
('SW-0002', '{"id":"SW-0002","userId":"USR-002","facilityId":"FAC-001","roomId":"ROOM-002","status":"Active","battery":62,"heartRate":78,"fallStatus":"NoFall","fallProbability":0.02,"connectionStatus":"Good","rssi":-68,"lastUpdatedUtc":"2026-09-21T08:30:00Z","lastSyncUtc":"2026-09-21T08:30:00Z","firmwareVersion":"v1.2.4"}'::jsonb),
('SW-0003', '{"id":"SW-0003","userId":"USR-003","facilityId":"FAC-002","roomId":"ROOM-003","status":"LowBattery","battery":15,"heartRate":82,"fallStatus":"NoFall","fallProbability":0.03,"connectionStatus":"Weak","rssi":-85,"lastUpdatedUtc":"2026-09-21T08:30:00Z","lastSyncUtc":"2026-09-21T08:15:00Z","firmwareVersion":"v1.2.3"}'::jsonb);

-- Gắn ngược deviceId vào residents
UPDATE "residents" SET "data" = jsonb_set("data", '{deviceId}', '"SW-0001"'::jsonb) WHERE "id" = 'USR-001';
UPDATE "residents" SET "data" = jsonb_set("data", '{deviceId}', '"SW-0002"'::jsonb) WHERE "id" = 'USR-002';
UPDATE "residents" SET "data" = jsonb_set("data", '{deviceId}', '"SW-0003"'::jsonb) WHERE "id" = 'USR-003';

-- ---------------------------------------------------------------------
-- 6. ASSIGNMENTS
-- ---------------------------------------------------------------------
INSERT INTO "assignments" ("id","data") VALUES
('ASN-001', '{"id":"ASN-001","deviceId":"SW-0001","userId":"USR-001","assignedAtUtc":"2026-09-01T08:00:00Z","isActive":true}'::jsonb),
('ASN-002', '{"id":"ASN-002","deviceId":"SW-0002","userId":"USR-002","assignedAtUtc":"2026-09-05T08:00:00Z","isActive":true}'::jsonb),
('ASN-003', '{"id":"ASN-003","deviceId":"SW-0003","userId":"USR-003","assignedAtUtc":"2026-09-10T08:00:00Z","isActive":true}'::jsonb);

-- ---------------------------------------------------------------------
-- 7. TELEMETRY
-- ---------------------------------------------------------------------
INSERT INTO "telemetry_records" ("event_at","data")
VALUES
-- SW-0001
('2026-09-21T08:30:00Z', '{"deviceId":"SW-0001","timestampUtc":"2026-09-21T08:30:00Z","heartRate":72,"battery":86,"fallStatus":"NoFall","fallProbability":0.01,"alertLevel":"Low","connectionStatus":"Good","rssi":-60,"accelX":0.12,"accelY":0.08,"accelZ":9.72,"gyroX":0.01,"gyroY":0.02,"gyroZ":0.01}'::jsonb),
('2026-09-21T08:35:00Z', '{"deviceId":"SW-0001","timestampUtc":"2026-09-21T08:35:00Z","heartRate":75,"battery":86,"fallStatus":"NoFall","fallProbability":0.01,"alertLevel":"Low","connectionStatus":"Good","rssi":-60,"accelX":0.10,"accelY":0.05,"accelZ":9.75,"gyroX":0.02,"gyroY":0.01,"gyroZ":0.00}'::jsonb),
-- SW-0002
('2026-09-21T08:30:00Z', '{"deviceId":"SW-0002","timestampUtc":"2026-09-21T08:30:00Z","heartRate":78,"battery":62,"fallStatus":"NoFall","fallProbability":0.02,"alertLevel":"Low","connectionStatus":"Good","rssi":-68,"accelX":0.11,"accelY":0.09,"accelZ":9.70,"gyroX":0.01,"gyroY":0.03,"gyroZ":0.02}'::jsonb),
('2026-09-21T08:35:00Z', '{"deviceId":"SW-0002","timestampUtc":"2026-09-21T08:35:00Z","heartRate":80,"battery":62,"fallStatus":"NoFall","fallProbability":0.02,"alertLevel":"Low","connectionStatus":"Good","rssi":-68,"accelX":0.13,"accelY":0.07,"accelZ":9.71,"gyroX":0.01,"gyroY":0.02,"gyroZ":0.01}'::jsonb),
-- SW-0003
('2026-09-21T08:30:00Z', '{"deviceId":"SW-0003","timestampUtc":"2026-09-21T08:30:00Z","heartRate":82,"battery":15,"fallStatus":"NoFall","fallProbability":0.03,"alertLevel":"Medium","connectionStatus":"Weak","rssi":-85,"accelX":0.15,"accelY":0.10,"accelZ":9.65,"gyroX":0.03,"gyroY":0.02,"gyroZ":0.01}'::jsonb),
('2026-09-21T08:35:00Z', '{"deviceId":"SW-0003","timestampUtc":"2026-09-21T08:35:00Z","heartRate":84,"battery":15,"fallStatus":"NoFall","fallProbability":0.03,"alertLevel":"Medium","connectionStatus":"Weak","rssi":-85,"accelX":0.14,"accelY":0.11,"accelZ":9.66,"gyroX":0.02,"gyroY":0.03,"gyroZ":0.02}'::jsonb);

-- ---------------------------------------------------------------------
-- 8. ALERTS
-- ---------------------------------------------------------------------
INSERT INTO "alerts" ("id","data")
VALUES
('ALERT-001', '{"id":"ALERT-001","type":"Fall","severity":"High","status":"Open","deviceId":"SW-0001","userId":"USR-001","facilityId":"FAC-001","roomId":"ROOM-001","message":"Phát hiện té ngã","eventAtUtc":"2026-09-21T08:35:00Z","createdAtUtc":"2026-09-21T08:35:01Z","updatedAtUtc":"2026-09-21T08:35:01Z","handledByStaffId":null,"isUrgent":true,"notes":null,"audits":[]}'::jsonb),

('ALERT-002', '{"id":"ALERT-002","type":"LowBattery","severity":"Medium","status":"Acknowledged","deviceId":"SW-0003","userId":"USR-003","facilityId":"FAC-002","roomId":"ROOM-003","message":"Pin thiết bị dưới 20%","eventAtUtc":"2026-09-21T08:20:00Z","createdAtUtc":"2026-09-21T08:20:05Z","updatedAtUtc":"2026-09-21T08:25:00Z","handledByStaffId":"STAFF-003","isUrgent":false,"notes":"Đã thông báo cho điều dưỡng thay pin","audits":[]}'::jsonb),

('ALERT-003', '{"id":"ALERT-003","type":"HeartRate","severity":"High","status":"Closed","deviceId":"SW-0002","userId":"USR-002","facilityId":"FAC-001","roomId":"ROOM-002","message":"Nhịp tim vượt ngưỡng 100 bpm","eventAtUtc":"2026-09-20T22:10:00Z","createdAtUtc":"2026-09-20T22:10:02Z","updatedAtUtc":"2026-09-20T22:40:00Z","handledByStaffId":"STAFF-001","isUrgent":false,"notes":"Đã kiểm tra, nhịp tim ổn định trở lại","audits":[]}'::jsonb);

COMMIT;

-- ---------------------------------------------------------------------
-- KIỂM TRA NHANH
-- ---------------------------------------------------------------------
-- SELECT 'facilities' AS t, COUNT(*) FROM "facilities"
-- UNION ALL SELECT 'rooms',       COUNT(*) FROM "rooms"
-- UNION ALL SELECT 'staff',       COUNT(*) FROM "staff"
-- UNION ALL SELECT 'residents',   COUNT(*) FROM "residents"
-- UNION ALL SELECT 'devices',     COUNT(*) FROM "devices"
-- UNION ALL SELECT 'assignments', COUNT(*) FROM "assignments"
-- UNION ALL SELECT 'telemetry_records', COUNT(*) FROM "telemetry_records"
-- UNION ALL SELECT 'alerts',      COUNT(*) FROM "alerts";