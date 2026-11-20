-- Update only the two demo facility records; this does not reset other data.
DO $$
DECLARE
  affected_rows integer;
BEGIN
  UPDATE "facilities"
  SET "data" = jsonb_set(
    jsonb_set(
      jsonb_set(
        jsonb_set(
          "data",
          '{name}',
          to_jsonb('Viện dưỡng lão Diên Hồng - Cơ sở 1'::text)
        ),
        '{address}',
        to_jsonb('U07-L16, Khu đô thị mới Dương Nội, Yên Nghĩa, Hà Nội'::text)
      ),
      '{latitude}',
      '20.9565885'::jsonb
    ),
    '{longitude}',
    '105.7357884'::jsonb
  ),
  "updated_at" = now()
  WHERE "id" = 'FAC-001';

  GET DIAGNOSTICS affected_rows = ROW_COUNT;
  IF affected_rows <> 1 THEN
    RAISE EXCEPTION 'Expected to update FAC-001 once, updated % rows', affected_rows;
  END IF;

  UPDATE "facilities"
  SET "data" = jsonb_set(
    jsonb_set(
      jsonb_set(
        jsonb_set(
          jsonb_set(
            "data",
            '{name}',
            to_jsonb('Viện dưỡng lão Diên Hồng - Cơ sở 2'::text)
          ),
          '{address}',
          to_jsonb('A2.3-LK05-Ô số 18, Khu đô thị Thanh Hà Cienco5, Bình Minh, Hà Nội'::text)
        ),
        '{latitude}',
        '20.9261211'::jsonb
      ),
      '{longitude}',
      '105.782661'::jsonb
    ),
    '{phone}',
    to_jsonb('0981126507'::text)
  ),
  "updated_at" = now()
  WHERE "id" = 'FAC-002';

  GET DIAGNOSTICS affected_rows = ROW_COUNT;
  IF affected_rows <> 1 THEN
    RAISE EXCEPTION 'Expected to update FAC-002 once, updated % rows', affected_rows;
  END IF;
END;
$$;
