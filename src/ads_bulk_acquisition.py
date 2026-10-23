"""Persistent ADS acquisition and native GRIB QC; no model or as-of certification."""
import csv  # ส่งออกแผนและผลตรวจโดยไม่แก้ค่าดิบ
import hashlib  # ตรวจไฟล์ก่อนใช้ซ้ำ
import importlib.metadata  # บันทึกรุ่นเครื่องมือที่ใช้จริง
import json  # เก็บแผน คำขอ และหลักฐาน
import math  # ตรวจค่าจำกัดและระยะกริด
import os  # ย้ายไฟล์ชั่วคราวเป็นไฟล์ที่บันทึกครบ
import platform  # บันทึกรุ่น Python
import time  # เว้นระยะตรวจสถานะคิว
import zipfile  # ส่งออกเฉพาะไฟล์ที่กำหนด
from collections import defaultdict  # ตรวจความครบเป็นรายรอบและรายวัน
from datetime import date, datetime, timedelta, timezone  # แยกช่วง UTC จากวันไทย
from pathlib import Path  # จำกัดไฟล์ทั้งหมดไว้ในโฟลเดอร์โครงการ
import eccodes as ec  # อ่าน GRIB จริง ไม่อนุมานเวลาจากชื่อไฟล์

UTC = timezone.utc  # ระบบเวลาของรอบต้นทาง
THAI = timezone(timedelta(hours=7))  # วันเป้าหมายตามเวลาไทย
PM_DATASET = 'cams-global-atmospheric-composition-forecasts'  # ผลิตภัณฑ์ PM ที่ผ่าน pilot
FIRE_DATASET = 'cams-global-fire-emissions-gfas'  # ผลิตภัณฑ์ไฟตัวเลือกที่ผ่าน pilot
PM_AREA = [19.2, 98.4, 18.4, 99.6]  # ขอบเขต PM เหมือน pilot
FIRE_AREA = [21.0, 97.0, 17.5, 101.0]  # ขอบเขตไฟเหมือน pilot
RECEPTOR = (18.7883, 98.9853)  # จุดศึกษาเชียงใหม่เดิม
EXPECTED_PM_POINT = (18.8, 98.8)  # จุดใกล้ที่สุดที่ยืนยันจากไฟล์จริงแล้ว

def require(condition, message):  # กฎตรวจต้องทำงานแม้ปิด assert
    if not condition:  # หยุดเมื่อข้อมูลหรือหลักฐานไม่ครบ
        raise ValueError(message)  # ไม่ส่งผลผิดเป็นสถานะสำเร็จ

def utc_now():  # เวลาที่ดำเนินการปัจจุบัน ไม่ใช่เวลาเผยแพร่ย้อนหลัง
    return datetime.now(UTC).isoformat()  # เก็บ timezone ชัดเจน

def digest(path):  # ตรวจไฟล์โดยไม่อ่านทั้งไฟล์เข้าหน่วยความจำ
    result = hashlib.sha256()  # ใช้ SHA-256 เดียวกันทั้งระบบ
    with Path(path).open('rb') as stream:  # อ่านเฉพาะไฟล์ที่ระบุ
        for block in iter(lambda: stream.read(1024 * 1024), b''):  # แบ่งอ่านเป็นก้อน
            result.update(block)  # รวมทุกไบต์
    return result.hexdigest()  # ไม่ใช้เวลาสร้างไฟล์แทน hash

def canonical(value):  # ทำ hash ของโครงสร้างให้ไม่ขึ้นกับลำดับ key
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)  # รักษาค่าจริงทั้งหมด

def json_write(path, value):  # ลดโอกาสใช้ JSON ที่เขียนค้าง
    path = Path(path)  # รับพาธรูปแบบเดียวกัน
    temp = path.with_name(path.name + '.tmp')  # เขียนไฟล์ชั่วคราวในโฟลเดอร์เดียวกัน
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')  # ไม่บันทึก NaN
    os.replace(temp, path)  # เปลี่ยนชื่อเมื่อเขียนสำเร็จ ไม่รับรองความทนทานทุกกรณีของ Drive

def read_json(path):  # อ่านเฉพาะหลักฐานที่กำหนด
    return json.loads(Path(path).read_text(encoding='utf-8'))  # ไม่รัน source จากไฟล์ข้อมูล

def csv_write(path, rows):  # เก็บผลตรวจเพื่ออ่านนอก notebook
    if not rows:  # ไม่สร้างหัวตารางจากแถวที่ไม่มี
        return  # ไฟล์นี้จะสร้างเมื่อมีข้อมูลจริง
    with Path(path).open('w', newline='', encoding='utf-8-sig') as stream:  # รองรับหน่วยและภาษา
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))  # คอลัมน์สอดคล้องกับข้อมูล
        writer.writeheader()  # ระบุชื่อทุกตัวแปร
        writer.writerows(rows)  # ไม่เติมหรือลบแถวข้อมูล

def days(start, end):  # สร้างปฏิทินครบทุกวันรวมปลายทั้งสอง
    first, last = date.fromisoformat(start), date.fromisoformat(end)  # ตรวจรูปแบบวันที่
    require(first <= last, 'Reversed date range.')  # ไม่ให้แผนว่างโดยไม่รู้ตัว
    return [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]  # ไม่บีบวันหายทิ้ง

def make_plan():  # ล็อกขอบเขตก่อนดูผลหรือคะแนน
    settings = [('pm', PM_DATASET, '2023-12-23', '2025-12-30'), ('gfas', FIRE_DATASET, '2023-12-23', '2025-12-31')]  # เผื่อ history และ source offset ก่อนวันเป้าหมายแรก
    jobs = []  # คำขอเรียงตามผลิตภัณฑ์และเดือน
    for family, dataset, first, last in settings:  # แยกความหมายวันของแต่ละผลิตภัณฑ์
        groups = defaultdict(list)  # แบ่งขนาดคำขอเป็นรายเดือน
        for day in days(first, last):  # รวม leap day ตามปฏิทินจริง
            groups[day[:7]].append(day)  # ไม่ผสมเดือนหรือปี
        for month, dates in groups.items():  # ใช้ช่วงที่ต่อเนื่องภายในเดือน
            request = {'date': dates[0] + '/' + dates[-1], 'time': ['12:00'], 'variable': ['particulate_matter_2.5um'], 'leadtime_hour': [str(h) for h in range(5, 53)], 'type': ['forecast'], 'data_format': 'grib', 'area': PM_AREA.copy()} if family == 'pm' else {'date': dates[0] + '/' + dates[-1], 'time': ['00:00'], 'temporal_aggregation': ['daily'], 'variable': ['wildfire_radiative_power', 'wildfire_fraction_of_area_observed'], 'data_format': 'grib', 'area': FIRE_AREA.copy()}  # นำรูปแบบ pilot มาขยายตามเวลา
            jobs.append({'job_key': family + '_' + month, 'family': family, 'dataset': dataset, 'dates': dates, 'request': request})  # วัน PM คือวันเริ่มรอบ UTC; วันไฟคือวันเฉลี่ย UTC
    return {'schema': 1, 'purpose': 'Full-period feasibility acquisition; not a final model lock.', 'study_local_days': ['2024-01-01', '2025-12-31'], 'issue': 'D 07:00 Asia/Bangkok', 'target': 'P(D+1)', 'pm_profile': 'Run date r at 12 UTC, leads 5..28 -> local day r+1.', 'provider_reference': 'Same run r, leads 29..52 -> local day r+2; issue day r+1 at 07 Thai. Not a feature or station truth.', 'fire_clock': 'UTC daily means; nominal latest start date D-2 at issue D 07 Thai. ADS exceptions and revisions remain open.', 'jobs': jobs}  # ไม่สร้างรับรอง as-of จากแผน

def prepare(root, source_path):  # ใช้ root คงเดิมเพื่อ resume
    root = Path(root)  # อนุญาตเฉพาะพื้นที่ที่ผู้ใช้เลือก
    root.mkdir(parents=True, exist_ok=True)  # ไม่ลบโฟลเดอร์ก่อนหน้า
    plan = make_plan()  # แผนวิทยาศาสตร์จาก source นี้
    source_sha = hashlib.sha256(Path(source_path).read_text(encoding='utf-8').encode('utf-8')).hexdigest()  # ปรับ newline ข้ามระบบ
    lock = {'plan_sha256': hashlib.sha256(canonical(plan).encode('utf-8')).hexdigest(), 'source_normalized_utf8_sha256': source_sha}  # แยก lock acquisition จาก forecast lock
    if (root / 'acquisition_lock.json').exists():  # ต้องตรงกับรอบเดิมก่อนใช้ไฟล์ต่อ
        require(read_json(root / 'acquisition_lock.json') == lock, 'Acquisition plan/source changed. Use a new root; do not mix evidence.')  # ไม่จับ receipt เก่ามารับรอง source ใหม่
    else:  # สร้างรอบใหม่ในพื้นที่โครงการเท่านั้น
        require(not any(root.iterdir()), 'New acquisition root must be empty.')  # ไม่รับไฟล์เก่าที่ไม่มี lock
        json_write(root / 'acquisition_lock.json', lock)  # บันทึกก่อนสร้างงานย่อย
        json_write(root / 'plan.json', plan)  # แผนไม่มี token
        (root / 'ads_full_acquisition.py').write_text(Path(source_path).read_text(encoding='utf-8'), encoding='utf-8')  # source ที่ใช้จริง
    require(read_json(root / 'plan.json') == plan, 'Stored plan differs.')  # ป้องกันแก้แผนหลังล็อก
    versions = {'python': platform.python_version(), 'ecCodes_library': ec.codes_get_api_version()}  # บันทึกเครื่องมือจริงของ session
    for package in ('ecmwf-datastores-client', 'eccodes', 'numpy'):  # แยก direct tool กับไลบรารี
        versions[package] = importlib.metadata.version(package)  # ใช้รุ่นติดตั้งจริง
    sessions = root / 'sessions'  # เก็บ runtime หลายรอบโดยไม่เขียนหลักฐานเดิมทับ
    sessions.mkdir(exist_ok=True)  # การ resume ไม่เริ่มชุดข้อมูลใหม่
    stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')  # แยกชื่อ session
    json_write(sessions / (stamp + '.json'), {'recorded_at_utc': utc_now(), 'versions': versions, 'lock': lock})  # ไม่เก็บ environment credentials
    return plan  # ให้ notebook แสดงรายการก่อนส่งคำขอ

def boundary_count(path):  # ตรวจ binary ครบทุกไบต์
    count = 0  # เริ่มนับทุก message จริง
    with Path(path).open('rb') as stream:  # ไม่โหลด raw ทั้งช่วงไว้ในหน่วยความจำ
        size = Path(path).stat().st_size  # ขนาดไฟล์ที่ดาวน์โหลดจริง
        while stream.tell() < size:  # ไม่ข้าม bytes ส่วนเกิน
            offset = stream.tell()  # ตำแหน่งต้นข้อความ
            head = stream.read(16)  # ครอบคลุม header ของ GRIB1/2
            require(len(head) == 16 and head[:4] == b'GRIB' and head[7] in (1, 2), 'Invalid GRIB header.')  # ปฏิเสธ HTML/ZIP/ไฟล์เสีย
            length = int.from_bytes(head[4:7] if head[7] == 1 else head[8:16], 'big')  # ความยาวตาม edition
            require(length >= 20 and offset + length <= size, 'Truncated GRIB message.')  # ไม่ใช้ข้อมูลขาด
            stream.seek(offset + length - 4)  # ไปท้าย message โดยไม่แก้ไฟล์
            require(stream.read(4) == b'7777', 'Invalid GRIB end marker.')  # ตรวจข้อความจบครบ
            count += 1  # เก็บจำนวนที่ decoder ต้องอ่านได้ตรงกัน
    require(count > 0, 'Empty GRIB.')  # ไฟล์ว่างไม่ใช่ศูนย์ไฟ
    return count  # ไม่ใช้ชื่อไฟล์รับรองรูปแบบ

def distance(lat, lon):  # เลือกจุดศึกษาโดยระยะจริง
    y, x = RECEPTOR  # พิกัดเดียวกันทุกวัน
    a = math.sin(math.radians(lat-y)/2)**2 + math.cos(math.radians(y))*math.cos(math.radians(lat))*math.sin(math.radians(lon-x)/2)**2  # haversine
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1.0, a)))  # ระยะกิโลเมตร

def inspect_file(path, job):  # ตรวจข้อมูลโดยไม่ฝึกโมเดลหรือ fill/drop
    messages = boundary_count(path)  # ตรวจ raw framing ก่อน decode
    expected_dates = set(job['dates'])  # วันที่ต้องครบตามคำขอ
    seen, fields, hourly, daily = set(), [], [], []  # แยกหลักฐานไม่ให้ปนคำตอบกับ feature
    grids, per_run = {}, defaultdict(list)  # ตรวจกริดและความครบของแต่ละรอบ
    with Path(path).open('rb') as stream:  # อ่านรายข้อความให้ใช้หน่วยความจำจำกัด
        while True:  # ถอดทุก message แม้ provider ไม่เรียงเวลา
            handle = ec.codes_grib_new_from_file(stream)  # ใช้ ecCodes แทนการเดา binary
            if handle is None:  # จบข้อมูลจริง
                break  # ไม่สร้างแถวแทนวันหาย
            try:  # คืน handle เสมอ
                keys = ['centre', 'dataDate', 'dataTime', 'validityDate', 'validityTime', 'stepType', 'stepUnits', 'startStep', 'endStep', 'paramId', 'units', 'Ni', 'Nj', 'numberOfPoints', 'numberOfMissing', 'bitmapPresent', 'missingValue']  # metadata สำคัญต่อเวลา หน่วย และ missing
                meta = {key: ec.codes_get(handle, key) for key in keys}  # อ่านจาก raw
                run = datetime.strptime(str(meta['dataDate']) + f"{int(meta['dataTime']):04d}", '%Y%m%d%H%M').replace(tzinfo=UTC)  # วันเริ่มช่วงจาก metadata
                valid = datetime.strptime(str(meta['validityDate']) + f"{int(meta['validityTime']):04d}", '%Y%m%d%H%M').replace(tzinfo=UTC)  # เวลาที่ค่ามีผล ไม่ใช้เป็นวันเริ่มทุกผลิตภัณฑ์
                require(meta['centre'] == 'ecmf' and run.date().isoformat() in expected_dates, 'Unexpected provider/date.')  # ป้องกันช่วงเกินหรือผิดคำขอ
                lat = list(map(float, ec.codes_get_array(handle, 'latitudes')))  # พิกัดจริง
                lon = list(map(float, ec.codes_get_array(handle, 'longitudes')))  # พิกัดจริง
                values = list(map(float, ec.codes_get_values(handle)))  # รักษาหน่วยต้นฉบับ
                require(len(values) == len(lat) == len(lon) == int(meta['numberOfPoints']), 'Grid/value length mismatch.')  # ไม่ตัดทอนเงียบ ๆ
                grid = tuple(zip(lat, lon))  # รักษาลำดับค่ากับพิกัด
                require(len(set(grid)) == len(grid), 'Duplicate grid points.')  # กริดซ้ำต้องตรวจ
                reference = grids.setdefault(job['family'], grid)  # กริดเดียวกันภายในผลิตภัณฑ์/คำขอ
                require(grid == reference, 'Grid changed within a chunk; review before use.')  # ไม่เปลี่ยนพื้นที่โดยไม่แจ้ง
                bitmap = ec.codes_get_array(handle, 'bitmap') if meta['bitmapPresent'] else None  # แยก missing จากค่าศูนย์
                missing = [(bitmap[i] == 0 if bitmap is not None else (v == meta['missingValue'] if meta['numberOfMissing'] else False)) or not math.isfinite(v) for i, v in enumerate(values)]  # ไม่ fill ค่าที่ขาด
                clean = [v for v, bad in zip(values, missing) if not bad]  # ใช้เฉพาะเพื่อสถิติตรวจ ไม่ลบ raw
                require(all(v >= 0 for v in clean), 'Negative native PM/fire value; manual review required.')  # ไม่ clip ค่าผิดหลักโดยอัตโนมัติ
                meta.update(source_date=run.date().isoformat(), missing_or_nonfinite=sum(map(bool, missing)), zero_values=sum(v == 0 for v in clean), positive_values=sum(v > 0 for v in clean), minimum=min(clean) if clean else None, maximum=max(clean) if clean else None, latitude_min=min(lat), latitude_max=max(lat), longitude_min=min(lon), longitude_max=max(lon))  # สถิติเพื่อ QC ไม่ใช่ final feature
                if job['family'] == 'pm':  # PM ใช้รอบ 12 UTC และ hourly lead เท่านั้น
                    lead = int(meta['endStep'])  # อ่าน lead จริง
                    identity = {key: ec.codes_get(handle, key) for key in ['marsClass', 'marsType', 'experimentVersionNumber', 'typeOfLevel', 'level']}  # แยก forecast จาก analysis/reanalysis
                    require(identity['marsClass'] == 'mc' and identity['marsType'] == 'fc' and str(identity['experimentVersionNumber']) == '0001' and identity['typeOfLevel'] == 'surface' and identity['level'] == 0, 'Unexpected PM product identity.')  # ไม่เปลี่ยน vintage โดยเงียบ
                    meta.update(identity)  # เก็บหลักฐานผลิตภัณฑ์
                    require(meta['paramId'] == 210073 and meta['units'] == 'kg m**-3' and meta['stepType'] == 'instant', 'Unexpected PM parameter/unit/step type.')  # daily mean มาจาก hourly instantaneous samples
                    require(int(meta['Ni']) == 4 and int(meta['Nj']) == 3 and len(values) == 12 and all(any(abs(y-point) < 1e-5 for point in (18.4, 18.8, 19.2)) for y in lat) and all(any(abs(x-point) < 1e-5 for point in (98.4, 98.8, 99.2, 99.6)) for x in lon), 'PM native grid differs from the verified pilot.')  # หยุดเมื่อกริดต่าง ไม่ regrid อัตโนมัติ
                    require(run.hour == 12 and meta['stepUnits'] == 1 and 5 <= lead <= 52 and int(meta['startStep']) == lead and valid == run + timedelta(hours=lead), 'PM run/lead/valid mismatch.')  # ไม่รับ lead ที่ขาดหรือเหลื่อมเวลา
                    key = (run.isoformat(), lead)  # แยกรอบและชั่วโมง
                    near = min(range(len(values)), key=lambda i: (distance(lat[i], lon[i]), lat[i], lon[i]))  # จุดเดียวโดยไม่เลือกตาม PM
                    require(abs(lat[near]-EXPECTED_PM_POINT[0]) < 1e-5 and abs(lon[near]-EXPECTED_PM_POINT[1]) < 1e-5, 'Nearest PM point changed; spatial contract needs review.')  # หยุดเมื่อจุดศึกษาเปลี่ยน
                    role = 'fixed_vintage_profile' if lead <= 28 else 'provider_forecast_reference'  # แยก label/history profile จาก forecast benchmark
                    row = {'run_utc': run.isoformat(), 'lead_hours': lead, 'valid_utc': valid.isoformat(), 'valid_thailand': valid.astimezone(THAI).isoformat(), 'local_day': valid.astimezone(THAI).date().isoformat(), 'role': role, 'latitude': lat[near], 'longitude': lon[near], 'pm25_kg_m3': None if missing[near] else values[near], 'pm25_ug_m3': None if missing[near] else values[near] * 1e9, 'source_missing': bool(missing[near])}  # target ไม่ได้รับการเติมค่า
                    hourly.append(row)  # เก็บค่ารายชั่วโมงที่จุดศึกษา
                    per_run[(run.isoformat(), role)].append(row)  # รวบรวมเพื่อตรวจ 24 ชั่วโมง
                else:  # GFAS เป็นวัน UTC และ density ไม่ใช่ hotspot count
                    require(meta['paramId'] in (210099, 210097), 'Unexpected GFAS parameter.')  # รับเพียงสองตัวแปรที่ทดสอบแล้ว
                    expected_unit = 'W m**-2' if meta['paramId'] == 210099 else 'dimensionless'  # ไม่สับสนกำลังกับ density
                    require(meta['units'] == expected_unit and meta['stepType'] == 'avg' and meta['stepUnits'] == 1 and run.hour == 0 and meta['startStep'] == 0 and meta['endStep'] == 24 and valid == run + timedelta(days=1), 'GFAS unit/day interval mismatch.')  # validity เป็นปลายช่วง
                    require(int(meta['Ni']) == 40 and int(meta['Nj']) == 35 and len(values) == 1400 and len(set(lat)) == 35 and len(set(lon)) == 40 and abs(min(lat)-17.55) < 1e-5 and abs(max(lat)-20.95) < 1e-5 and abs(min(lon)-97.05) < 1e-5 and abs(max(lon)-100.95) < 1e-5, 'GFAS grid differs from the real pilot.')  # พื้นที่ต้องตรงกับ contract
                    key = (run.date().isoformat(), int(meta['paramId']))  # ทุกวันต้องมีสองตัวแปร
                    meta.update(interval_start_utc=run.isoformat(), interval_end_exclusive_utc=valid.isoformat(), values_above_one=sum(v > 1 for v in clean))  # เก็บ offire >1 โดยไม่ clip
                require(key not in seen, 'Duplicate field.')  # ไม่เฉลี่ยข้อมูลซ้ำ
                seen.add(key)  # เก็บทุก field ที่ผ่าน identity
                fields.append(meta)  # missing คงอยู่ในรายงานและ raw
            finally:  # ทำงานแม้การตรวจพบข้อผิดพลาด
                ec.codes_release(handle)  # คืนหน่วยความจำ
    expected = {(day, param) for day in expected_dates for param in (210099, 210097)} if job['family'] == 'gfas' else {(datetime.fromisoformat(day + 'T12:00:00+00:00').isoformat(), lead) for day in expected_dates for lead in range(5, 53)}  # ต้องมี field ตามคำขอครบ
    require(seen == expected and len(fields) == messages, 'Missing/unexpected fields or decoder count mismatch.')  # ไม่ถือว่าขาดทั้งวันเป็นศูนย์
    for (run, role), group in sorted(per_run.items()):  # สรุปวัน PM แยกตามบทบาท
        group.sort(key=lambda r: r['valid_utc'])  # ไม่เชื่อลำดับไฟล์
        complete = len(group) == 24 and len({r['valid_utc'] for r in group}) == 24 and len({r['local_day'] for r in group}) == 1 and not any(r['source_missing'] for r in group)  # ต้องครบเวลาและค่าจริง
        numbers = [r['pm25_ug_m3'] for r in group] if complete else []  # วัน incomplete ไม่สร้างค่าเฉลี่ยบางชั่วโมง
        daily.append({'run_utc': run, 'role': role, 'local_day': group[0]['local_day'], 'complete_24h': complete, 'missing_hour_count': sum(r['source_missing'] for r in group), 'mean_ug_m3': math.fsum(numbers)/24 if complete else None, 'minimum_ug_m3': min(numbers) if complete else None, 'maximum_ug_m3': max(numbers) if complete else None})  # ไม่มี imputation ของ target
    return {'status': 'RAW_IDENTITY_AND_FIELD_COVERAGE_PASS_VALUES_RECORDED_NOT_IMPUTED', 'job_key': job['job_key'], 'messages': messages, 'fields_with_missing_or_nonfinite': sum(row['missing_or_nonfinite'] > 0 for row in fields), 'missing_or_nonfinite_grid_values': sum(row['missing_or_nonfinite'] for row in fields), 'pm_incomplete_profiles': sum(not row['complete_24h'] for row in daily), 'fields': fields, 'pm_hourly': sorted(hourly, key=lambda r: (r['run_utc'], r['lead_hours'])), 'pm_daily': daily, 'project_fill_count': 0, 'project_drop_count': 0, 'historical_availability_certified': False}  # missing เป็นผล QC ไม่ใช่หลักฐาน availability

def verified_receipt(folder, job, lock):  # ตรวจหลักฐานก่อนข้ามไฟล์ที่มีอยู่
    receipt_path, raw = folder / 'transfer_receipt.json', folder / 'raw.grib'  # ไม่รับชื่อไฟล์อื่นแทน
    if not receipt_path.exists():  # ยังไม่มี transfer ที่ยืนยัน
        return None  # ให้ runner จัดการ job state เดิม
    receipt = read_json(receipt_path)  # อ่านเฉพาะ receipt ของรายการนี้
    require(receipt['job'] == job and receipt['lock'] == lock and raw.is_file() and raw.stat().st_size == receipt['bytes'] and digest(raw) == receipt['sha256'], 'Stored receipt/raw mismatch; do not overwrite or resubmit.')  # hash ผิดต้องตรวจ ไม่โหลดทับ
    return receipt  # เฉพาะไฟล์ที่ยืนยันได้เท่านั้น

def run_jobs(root, client, source_path, families=('gfas', 'pm'), max_new_jobs=1, recovery_ids=None, poll_seconds=30, emit=print):  # ควบคุมโหลดทีละคำขอ
    root = Path(root)  # root เดิมบน Drive
    plan = prepare(root, source_path)  # ตรวจ lock ก่อนใช้ state
    lock = read_json(root / 'acquisition_lock.json')  # ผูก receipts กับ source/แผน
    require(set(families) <= {'gfas', 'pm'} and max_new_jobs > 0 and poll_seconds >= 1, 'Invalid runner settings.')  # ป้องกันพิมพ์ค่าผิดเงียบ ๆ
    recovery_ids, submitted = recovery_ids or {}, 0  # recovery ต้องระบุเลขจากบัญชี ADS เอง
    for job in sorted(plan['jobs'], key=lambda item: (0 if item['job_key'] in ('gfas_2023-12', 'pm_2023-12') else 1, list(families).index(item['family']) if item['family'] in families else 99, item['job_key'])):  # ตรวจคำขอแรกของทั้งสองผลิตภัณฑ์ก่อนทำเดือนถัดไป
        if job['family'] not in families:  # ไม่โหลดผลิตภัณฑ์ที่ไม่ได้เลือก
            continue  # เก็บงานอื่นไว้รอบถัดไป
        folder = root / 'jobs' / job['job_key']  # ชื่อสร้างจากแผน ไม่รับพาธภายนอก
        folder.mkdir(parents=True, exist_ok=True)  # resume โฟลเดอร์เดิม
        state_path = folder / 'job_state.json'  # เขียนก่อนและหลังส่งคำขอ
        receipt = verified_receipt(folder, job, lock)  # ตรวจ hash ก่อนตัดสินใจข้าม
        if receipt is not None:  # ไฟล์ดิบผ่าน transfer แล้ว
            if not (folder / 'qc.json').exists():  # หลุดหลัง transfer ให้ทำ QC ต่อ
                json_write(folder / 'qc.json', inspect_file(folder / 'raw.grib', job))  # ไม่ส่งคำขอใหม่
            emit(job['job_key'] + ': verified local file; no new request.')  # แสดงความคืบหน้าชัดเจน
            continue  # ไม่โหลดซ้ำ
        state = read_json(state_path) if state_path.exists() else None  # อ่านสถานะจากรอบก่อน
        if state is not None:  # ต้องเป็นงานตาม lock นี้
            require(state['job'] == job and state['lock'] == lock, 'Job-state plan/source mismatch.')  # ไม่ใช้เลขงานจากชุดอื่น
        if state is not None and not state.get('request_id'):  # การส่งก่อนหน้าอาจถึงเซิร์ฟเวอร์แล้ว
            request_id = recovery_ids.get(job['job_key'])  # ผู้ใช้ตรวจคำขอเดิมใน ADS ก่อน
            require(bool(request_id), 'Uncertain submission for ' + job['job_key'] + '. Check ADS requests; add its existing ID to RECOVERY_IDS. No automatic resubmission.')  # ป้องกันคำขอซ้ำในช่องว่างเครือข่าย
            remote = client.get_remote(request_id)  # กลับไปงานเดิม
            require(remote.collection_id == job['dataset'] and canonical(remote.request) == canonical(job['request']), 'Recovery ID request differs; inspect ADS normalization manually.')  # ไม่ผูกงานผิด แม้ provider normalize ต่างก็หยุดให้ตรวจ
            state.update(request_id=request_id, recovered_at_utc=utc_now())  # บันทึกเมื่อยืนยันแล้ว
            json_write(state_path, state)  # resume จะใช้เลขเดิม
        elif state is not None:  # มีเลขคำขอเดิมชัดเจน
            remote = client.get_remote(state['request_id'])  # ไม่ submit ใหม่
        else:  # ยังไม่เคยเริ่มส่งรายการนี้
            if submitted >= max_new_jobs:  # จำกัดจำนวนคำขอใหม่ใน session
                emit('New-request limit reached; rerun this cell to continue.')  # ไม่รายงานว่าทั้งช่วงครบแล้ว
                break  # งานคงเหลือไม่หาย
            state = {'job': job, 'lock': lock, 'phase': 'SUBMISSION_UNCERTAIN_UNTIL_ID_SAVED', 'submit_started_at_utc': utc_now(), 'request_id': None}  # บันทึกเจตนาก่อน POST
            json_write(state_path, state)  # ไม่เก็บ token ใน state
            emit(job['job_key'] + ': submitting one request.')  # แสดงว่าเริ่มขั้นไหน
            remote = client.submit(job['dataset'], job['request'])  # client ต้องตั้ง maximum_tries=1 เพื่อไม่ retry POST เงียบ ๆ
            state.update(request_id=remote.request_id, phase='SUBMITTED', request_id_recorded_at_utc=utc_now())  # ID สำหรับติดตามและ resume
            json_write(state_path, state)  # บันทึกก่อนรอคิว
            submitted += 1  # นับเฉพาะคำขอใหม่
        while True:  # รอเพียงงานเดียว ไม่ท่วมคิวด้วยงานพร้อมกัน
            status = remote.status  # อ่านสถานะล่าสุดจาก ADS
            state.update(last_status=status, last_checked_at_utc=utc_now())  # บันทึกจุด resume
            json_write(state_path, state)  # คงหมายเลขงานเดิม
            emit(job['job_key'] + ': ' + status + ' | request ID ' + state['request_id'])  # ไม่แสดง URL ดาวน์โหลดที่ลงนาม
            if status == 'successful':  # พร้อมโหลดผล
                break  # ไม่รอเพิ่มโดยไม่จำเป็น
            require(status in ('accepted', 'running', 'queued'), 'ADS job stopped: ' + status + '. Inspect its existing request; no automatic resubmission.')  # ไม่ปกปิด failed/rejected/expired
            time.sleep(poll_seconds)  # ใน Colab พักระหว่างตรวจคิว ไม่ใช่ ETA
        partial = folder / 'download.partial'  # ไม่ตั้งชื่อไฟล์สมบูรณ์ขณะยังโหลด
        if (folder / 'raw.grib').exists():  # อาจหลุดระหว่าง rename กับ receipt
            raise RuntimeError('Raw file exists without receipt. Preserve it and review before continuing.')  # ไม่ทับหลักฐานที่ยังไม่ยืนยัน
        remote.download(str(partial))  # ดาวน์โหลดผลของเลขงานเดิม; transfer ที่ขาดอาจเริ่มใหม่ แต่ไม่สร้าง ADS job ใหม่
        boundary_count(partial)  # ต้องเป็น GRIB ที่ครบทุก message ก่อน rename
        raw = folder / 'raw.grib'  # ชื่อคงที่ภายในงานนี้
        os.replace(partial, raw)  # ย้ายเมื่อ transfer จบและ framing ผ่าน
        receipt = {'job': job, 'lock': lock, 'request_id': state['request_id'], 'transfer_returned_at_utc': utc_now(), 'bytes': raw.stat().st_size, 'sha256': digest(raw), 'original_publication_time_observed': False}  # แยก transfer ปัจจุบันจากเวลาพร้อมใช้ย้อนหลัง
        json_write(folder / 'transfer_receipt.json', receipt)  # เก็บแม้ scientific QC ยังต้องตรวจ
        qc = inspect_file(raw, job)  # ตรวจเวลา หน่วย กริด จำนวน และ missing
        json_write(folder / 'qc.json', qc)  # ค่าที่ขาดถูกบันทึก ไม่เติม
        emit(job['job_key'] + ': transfer and native QC completed.')  # ไม่กล่าวว่า as-of ผ่าน
    return audit_local(root, source_path)  # สรุปตามไฟล์ที่ตรวจได้จริง

def audit_local(root, source_path):  # ตรวจหลักฐานใหม่ ไม่เชื่อ qc เก่าอย่างเดียว
    root = Path(root)  # พื้นที่รอบนี้
    plan = prepare(root, source_path)  # ตรวจ source/plan lock
    lock = read_json(root / 'acquisition_lock.json')  # receipts ต้องอ้าง lock เดียวกัน
    ledger, hourly, daily, all_fields = [], [], [], []  # สร้างตารางจาก raw ชุดเดียวกัน
    eligible = []  # ตรวจ coverage ไม่ใช่ as-of certification
    for job in plan['jobs']:  # รายการขาดต้องยังปรากฏ
        folder = root / 'jobs' / job['job_key']  # ไม่อ่านโฟลเดอร์อื่น
        receipt = verified_receipt(folder, job, lock)  # ไฟล์ไม่ครบจะไม่ผ่าน
        row = {'job_key': job['job_key'], 'family': job['family'], 'first_source_date': job['dates'][0], 'last_source_date': job['dates'][-1], 'source_days': len(job['dates']), 'downloaded_and_checked': False, 'messages': 0, 'missing_grid_values': None}  # None ไม่เท่ากับศูนย์
        if receipt is not None:  # ถอด raw ซ้ำเพื่อป้องกัน qc เก่าถูกแก้
            qc = inspect_file(folder / 'raw.grib', job)  # ตรวจ code path เดียวกับหลังโหลด
            if (folder / 'qc.json').exists():  # การ resume ต้องไม่ใช้ summary ที่ไม่ตรง raw
                require(read_json(folder / 'qc.json') == qc, 'Stored QC differs from raw recheck.')  # ไม่เชื่อไฟล์ผลลัพธ์อย่างเดียว
            else:  # กู้ขั้น QC ที่ยังไม่เคยจบ
                json_write(folder / 'qc.json', qc)  # ไม่สร้าง receipt transfer ใหม่
            row.update(downloaded_and_checked=True, messages=qc['messages'], missing_grid_values=qc['missing_or_nonfinite_grid_values'])  # ไม่เปลี่ยน missing เป็น zero-fill
            hourly.extend(qc['pm_hourly'])  # hourly profile และ benchmark แยก role
            daily.extend(qc['pm_daily'])  # วัน missing ไม่มี mean
            all_fields.extend(dict(field, family=job['family'], job_key=job['job_key']) for field in qc['fields'])  # บันทึกทุก field
        ledger.append(row)  # ครบทุกรายการ รวมที่ยังไม่โหลด
    pmap = {r['local_day']: r for r in daily if r['role'] == 'fixed_vintage_profile'}  # profile ตามกฎ P(d)
    bmap = {r['local_day']: r for r in daily if r['role'] == 'provider_forecast_reference'}  # baseline forecast แยกจาก label
    fire = defaultdict(dict)  # ทุกวันต้องมี FRP และ offire
    for row in all_fields:  # สร้างไฟ ledger จาก metadata จริง
        if row['family'] == 'gfas':  # ไม่ผสม unit/กริดกับ PM
            fire[row['source_date']][row['paramId']] = row  # พารามิเตอร์ไม่ซ้ำผ่าน QC แล้ว
    for target in days('2024-01-01', '2025-12-31'):  # หนึ่งแถวต่อวันเป้าหมาย ไม่ใช้กริดนับแทนวัน
        tday = date.fromisoformat(target)  # เวลาเป้าหมายตามวันไทย
        issue = tday - timedelta(days=1)  # ทำนายวันพรุ่งนี้
        pm_days = [(issue-timedelta(days=k)).isoformat() for k in range(1, 8)]  # หน้าต่างสูงสุด 7 วัน
        fire_days = [(issue-timedelta(days=k)).isoformat() for k in range(2, 9)]  # ไฟสิ้นสุดที่ UTC D-2 ตาม nominal schedule
        pm_ok = target in pmap and pmap[target]['complete_24h'] and all(d in pmap and pmap[d]['complete_24h'] for d in pm_days)  # target ไม่ถูกเติม
        fire_ok = all(set(fire[d]) == {210099, 210097} and all(field['missing_or_nonfinite'] == 0 for field in fire[d].values()) for d in fire_days)  # วันขาดไม่ถือศูนย์ไฟ
        eligible.append({'target_local_day': target, 'issue_local_day': issue.isoformat(), 'pm_target_and_7day_history_complete': pm_ok, 'gfas_7day_nominal_history_complete': fire_ok, 'provider_reference_complete': target in bmap and bmap[target]['complete_24h'], 'weather_join_performed': False, 'historical_availability_certified': False, 'final_common_cohort_eligible': None})  # ยังไม่ตัดสิน cohort สุดท้าย
    csv_write(root / 'download_ledger.csv', ledger)  # จำนวนคำขอที่เหลือ
    csv_write(root / 'pm_nearest_hourly.csv', hourly)  # ค่าจริงและ role ชัดเจน
    csv_write(root / 'pm_daily_profiles.csv', daily)  # มีทั้ง P และ provider reference
    csv_write(root / 'source_coverage_calendar.csv', eligible)  # ช่วงวันไม่ครบยังอยู่
    json_write(root / 'field_metadata.json', all_fields)  # เก็บ temporal/spatial metadata ทุก field
    complete = all(row['downloaded_and_checked'] for row in ledger)  # ต้องได้ครบทุกคำขอจริง
    summary = {'status': 'ALL_REQUESTS_TRANSFERRED_AND_RAW_QC_CHECKED' if complete else 'PARTIAL_ACQUISITION_NOT_COMPLETE', 'checked_at_utc': utc_now(), 'planned_requests': len(ledger), 'checked_requests': sum(row['downloaded_and_checked'] for row in ledger), 'remaining_requests': sum(not row['downloaded_and_checked'] for row in ledger), 'all_raw_transfers_and_field_coverage_complete': complete, 'fields_with_missing_or_nonfinite': sum(row['missing_or_nonfinite'] > 0 for row in all_fields), 'pm_and_fire_7day_coverage_candidate_target_days': sum(row['pm_target_and_7day_history_complete'] and row['gfas_7day_nominal_history_complete'] for row in eligible), 'actual_weather_joined_common_rows': None, 'historical_availability_certified': False, 'full_primary_experiment_gate_passed': False, 'models_rerun': False, 'project_fill_count': 0, 'project_drop_count': 0, 'scope': 'Acquisition and coverage only; source revisions, availability and the actual shared cohort remain to be reviewed.'}  # ไม่ยกระดับ coverage เป็น operational readiness
    json_write(root / 'acquisition_summary.json', summary)  # notebook แสดงสถานะเดียวกับ export
    return summary  # ให้ผู้ใช้รู้ว่ายังเหลือเท่าไร

def export_evidence(root, source_path):  # ส่งออกครบหรือบางส่วนพร้อมสถานะตรงจริง
    root = Path(root)  # โฟลเดอร์ที่มี lock เท่านั้น
    summary = audit_local(root, source_path)  # recheck ก่อนส่ง
    names = {'acquisition_lock.json', 'plan.json', 'ads_full_acquisition.py', 'download_ledger.csv', 'source_coverage_calendar.csv', 'field_metadata.json', 'acquisition_summary.json'}  # allowlist ไม่กวาด credentials
    for optional in ('pm_nearest_hourly.csv', 'pm_daily_profiles.csv'):  # PM อาจยังไม่โหลดในช่วงแรก
        if (root / optional).exists():  # ใส่เฉพาะตารางที่มีจริง
            names.add(optional)  # ไม่สร้างข้อมูลว่างแทนของจริง
    names.update(path.relative_to(root).as_posix() for path in (root / 'sessions').glob('*.json'))  # runtime versions ไม่มี token
    for job in make_plan()['jobs']:  # ใส่ไฟล์เฉพาะงานตามแผน
        folder = root / 'jobs' / job['job_key']  # ไม่อ่านไฟล์อื่นใน Drive
        for filename in ('job_state.json', 'raw.grib', 'transfer_receipt.json', 'qc.json'):  # partial transfer ไม่ส่งเป็น raw สำเร็จ
            path = folder / filename  # ตรวจไฟล์จริง
            if path.is_file():  # รองรับ partial package เพื่อช่วยวินิจฉัย
                names.add(path.relative_to(root).as_posix())  # ระบุสถานะด้วย summary
    manifest = {name: digest(root / name) for name in sorted(names)}  # ทุก payload มี hash
    json_write(root / 'manifest.json', manifest)  # manifest ไม่อ้าง hash ตัวเอง
    stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')  # ไม่ทับ export ก่อนหน้า
    archive = root.parent / ('PM25_ADS_FULL_' + ('COMPLETE_' if summary['all_raw_transfers_and_field_coverage_complete'] else 'PARTIAL_') + stamp + '.zip')  # ไม่ตั้งชื่อ complete เมื่อยังโหลดไม่ครบ
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:  # เก็บ raw โดยไม่เปลี่ยนเนื้อหา
        for name in sorted(names | {'manifest.json'}):  # allowlist เท่านั้น
            bundle.write(root / name, arcname=name)  # พาธภายในไม่ออกนอก root
    with zipfile.ZipFile(archive) as bundle:  # ตรวจ archive จริงหลังสร้าง
        require(bundle.testzip() is None, 'Export CRC failed.')  # ไม่ส่ง ZIP เสีย
        require(all(hashlib.sha256(bundle.read(name)).hexdigest() == value for name, value in manifest.items()), 'Export manifest mismatch.')  # ตรวจไบต์ใน ZIP ไม่ใช่แค่ต้นทาง
    return str(archive), summary  # ไม่ลบ raw หรือ job ฝั่ง ADS

import re  # ปกปิดข้อมูลลับในข้อความผิดพลาด

def safe_http_details(error, secret):  # เก็บเฉพาะสถานะและข้อความวินิจฉัยที่ผ่านการปกปิด
    current, seen, response = error, set(), None  # เตรียมค้นหา HTTP response จากลำดับข้อผิดพลาด
    while current is not None and id(current) not in seen:  # ป้องกันลำดับข้อผิดพลาดวนซ้ำ
        seen.add(id(current))  # บันทึกข้อผิดพลาดที่ตรวจแล้ว
        candidate = getattr(current, "response", None)  # อ่าน response หากไลบรารีแนบมา
        if candidate is not None:  # ห้ามใช้ค่าความจริงของ response เพราะ HTTP error อาจมีค่า False
            response = candidate  # เก็บ response จริง
            break  # พบหลักฐาน HTTP แล้ว
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)  # ตรวจข้อผิดพลาดต้นทางต่อ
    status = getattr(response, "status_code", None)  # ไม่เดารหัสเมื่อไม่มี response
    detail = "No structured server detail available."  # ไม่แสดง raw traceback หรือ HTML
    if response is not None:  # อ่านเฉพาะคำตอบ JSON ของเซิร์ฟเวอร์
        try:  # รองรับกรณีคำตอบไม่ใช่ JSON
            payload = response.json()  # อ่านข้อมูลในหน่วยความจำโดยไม่พิมพ์ทั้งก้อน
            if isinstance(payload, dict):  # รับเฉพาะรูปแบบที่คาดไว้
                values = [payload.get(name) for name in ("title", "detail", "message")]  # เลือกเฉพาะฟิลด์เหตุผล
                text_values = [value for value in values if isinstance(value, str)]  # ไม่ส่งออกโครงสร้างที่อาจมีคำขอหรือส่วนหัว
                if text_values:  # ใช้ข้อความจริงเมื่อเซิร์ฟเวอร์มีให้
                    detail = " | ".join(text_values)  # รวมข้อความวินิจฉัย
        except (ValueError, TypeError, AttributeError):  # ไม่อ่าน HTML หรือข้อมูลที่ผิดรูปแบบ
            pass  # คงข้อความอธิบายว่าไม่มีรายละเอียดแบบ JSON
    if secret:  # ปกปิดโทเคนที่ใช้จริงก่อนแสดงข้อมูล
        detail = re.sub(re.escape(secret), "[REDACTED]", detail, flags=re.IGNORECASE)  # ไม่แสดงค่าความลับแม้เซิร์ฟเวอร์สะท้อนกลับมา
    detail = re.sub(r"https?://[^\s<>]+", "[URL REDACTED]", detail)  # ไม่แสดง URL ซึ่งอาจมีค่าลับใน query
    detail = re.sub(r"(?i)\b(?:bearer|token|key|authorization)\b\s*[:=]?\s*[^\s,;]+", "[CREDENTIAL REDACTED]", detail)  # ปกปิดค่าที่มีป้ายกำกับความลับ
    detail = re.sub(r"[A-Za-z0-9_-]{24,}", "[LONG VALUE REDACTED]", detail)  # ปกปิดรหัสยาวอื่นที่อาจเป็นความลับ
    detail = re.sub(r"[\x00-\x1f\x7f]", " ", detail)[:1200]  # จำกัดความยาวและตัดอักขระควบคุม
    return {"error_type": type(error).__name__, "http_status": status, "server_detail_redacted": detail}

def safe_error(error, secret):  # แสดงเหตุผลที่อ่านได้โดยไม่พิมพ์ raw traceback
    result = safe_http_details(error, secret)  # เลือก HTTP detail ที่ผ่านการปกปิด
    if result['http_status'] is None:  # ข้อผิดพลาด local อาจไม่มี HTTP response
        detail = str(error)  # เก็บเหตุผลกฎตรวจให้ผู้ใช้ทราบ
        if secret:  # ปกปิด token ที่ใช้จริงก่อนแสดง
            detail = re.sub(re.escape(secret), '[REDACTED]', detail, flags=re.IGNORECASE)  # ไม่แสดงค่าลับที่สะท้อนกลับมา
        detail = re.sub(r'https?://[^\s<>]+', '[URL REDACTED]', detail)  # ไม่แสดง signed links
        detail = re.sub(r'(?i)\b(?:bearer|token|key|authorization)\b\s*[:=]?\s*[^\s,;]+', '[CREDENTIAL REDACTED]', detail)  # ปกปิดค่าที่มีป้าย credentials
        detail = re.sub(r'[A-Za-z0-9_-]{24,}', '[LONG VALUE REDACTED]', detail)  # ปกปิดรหัสยาวอื่น
        result['server_detail_redacted'] = re.sub(r'[\x00-\x1f\x7f]', ' ', detail)[:1200]  # จำกัดความยาวและตัด control characters
    return result  # ไม่มี raw request headers หรือ config
