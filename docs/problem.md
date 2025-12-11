# 문제점 및 개선 사항

## 1. 데이터 품질 이슈

### 1.1 담보명(coverage_name) 데이터 오염

**발견 일시**: 2025-12-11

**문제 상황**:
DB의 `coverage` 테이블에 잘못된 담보명이 포함되어 있음

**구체적인 예시**:
```
119 뇌졸중진단비
121 뇌출혈진단비
10년
15년
[갱신형]가족 일상생활중 배상책임Ⅱ
```

**문제 유형**:
1. **조항 번호가 담보명으로 저장됨**: "119", "121" 등
2. **기간 정보가 담보명으로 저장됨**: "10년", "15년" 등
3. **너무 짧은 담보명**: 3자 미만의 의미 없는 데이터
4. **형식 불일치**: 일부는 "[갱신형]" 접두사 포함, 일부는 미포함

**영향 범위**:
- `/api/companies/{company_name}/coverages` API
- InfoQueryBuilder 담보 선택 UI
- 사용자 경험 저하 (무의미한 담보명 표시)

**임시 해결책** (2025-12-11 적용):
`api/server.py`의 `get_company_coverages()` 함수에 필터링 로직 추가
```python
# 잘못된 데이터 필터링
# 1. 숫자로만 구성된 담보명 제외
# 2. "10년", "15년" 같은 기간 데이터 제외
# 3. 너무 짧은 담보명 제외 (3자 미만)
if not coverage_name or len(coverage_name.strip()) < 3:
    continue

coverage_stripped = coverage_name.strip()

# 숫자로 시작하는 경우 (조항 번호 등)
if coverage_stripped[0].isdigit():
    # "10년형" 같은 기간 데이터 제외
    if "년" in coverage_stripped and len(coverage_stripped) <= 4:
        continue
    # "119", "121" 같은 순수 숫자 제외
    if coverage_stripped.split()[0].isdigit():
        continue
```

**근본 해결 방안** (TODO):
1. **데이터 클렌징 스크립트 작성**
   - `coverage` 테이블 전수 조사
   - 잘못된 데이터 패턴 식별
   - 올바른 담보명으로 매핑 또는 삭제

2. **데이터 입력 검증 강화**
   - 원본 데이터 파싱 시 담보명 검증 로직 추가
   - 최소 길이, 형식 규칙 정의
   - 조항 번호와 담보명 분리

3. **DB 스키마 개선 고려**
   ```sql
   ALTER TABLE coverage
   ADD COLUMN clause_number VARCHAR(50),  -- 조항 번호 별도 컬럼
   ADD COLUMN coverage_period VARCHAR(20); -- 기간 정보 별도 컬럼
   ```

4. **데이터 정규화**
   - 담보명 표준화 규칙 수립
   - "[갱신형]", "[비갱신형]" 등은 별도 플래그로 관리

**우선순위**: 중
**담당**: TBD
**예상 작업 시간**: 4-8시간

---

## 2. 향후 발견될 문제점

(여기에 새로운 문제점 추가)

---

## 변경 이력

| 일자 | 문제 | 조치 | 담당자 |
|------|------|------|--------|
| 2025-12-11 | 담보명 데이터 오염 | API 레벨 필터링 추가 | Claude |
