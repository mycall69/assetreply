# 공공데이터포털 실제 응답 픽스처 (009 T001)

계약 테스트가 쓰는 **실제 응답 본문**이다. 요청 URL은 저장하지 않았다 — 인증키가 질의 문자열(`serviceKey`)에 들어가기
때문이다. 저장한 뒤 모든 파일에 `.env`의 `DATA_API_KEY`(날 것·퍼센트 인코딩 둘 다)가 없음을 검사했다(0건). 받은 스크립트는
저장소에 넣지 않았다(일회성). 키 자리는 아래에서 `{key}`로 적는다.

## 법정동코드 — 행정안전부 `StanReginCd` (2026-10-05)

요청: `https://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList?serviceKey={key}&type=json&pageNo=1&numOfRows=1000&locatadd_nm=<지역>`

| 파일 | `locatadd_nm` | `totalCount` | 비고 |
|------|---------------|--------------|------|
| `region_seoul.json` | 서울특별시 | 493 | 시·도 1 + 구 25 + 법정동. 리 없음 |
| `region_suwon.json` | 경기도 수원시 | 61 | 일반시(41110) 아래 구(41111…) |
| `region_chuncheon.json` | 강원특별자치도 춘천시 | 118 | 개편 뒤 새 코드(51110…). 리(`ri_cd ≠ 00`) 78행 포함 |
| `region_gangwon_old.json` | 강원도 | — | `{"RESULT":{"resultCode":"INFO-3","resultMsg":"데이터없음 에러"}}` — **폐지 코드는 주지 않는다** |

- 형식: `type=json`은 `Content-Type: text/html`이지만 본문은 JSON이다. 코드는 모두 문자열(`"region_cd":"1171000000"`),
  `locat_order`만 숫자. `{"StanReginCd":[{"head":[{"totalCount":N},{…},{"RESULT":{"resultCode":"INFO-0",…}}]},{"row":[…]}]}`
- 필드: `region_cd`(10자리), `sido_cd`, `sgg_cd`, `umd_cd`, `ri_cd`, `locatadd_nm`, `locathigh_cd`(상위 코드), `locallow_nm`(이름),
  `adpt_de`(적용일 — 개편된 곳만 값), `locat_rm`
- 전국(질의 없음)은 20,560행 — 1,000행씩 21쪽이다
- 결과 없음은 오류가 아니라 `INFO-3` — 폐지되었거나 없는 지역명

## 공동주택 단지 목록 — 국토교통부 `AptListService4` (2026-10-05)

요청: `https://apis.data.go.kr/1613000/AptListService4/getLegaldongAptList4?serviceKey={key}&bjdCode=<법정동 10자리>&pageNo=1&numOfRows=100`

| 파일 | `bjdCode` | `totalCount` |
|------|-----------|--------------|
| `kapt_list_1171010700.json` | 1171010700(서울 송파구 가락동) | 23 |
| `kapt_list_empty.json` | 9999999999 | 0 — `items: []`, `resultCode 00`(오류 아님) |

- 형식: JSON만 준다(`_type=xml`을 줘도 JSON). `{"response":{"body":{"items":[{"kaptCode","kaptName","bjdCode","as1"~"as4"}],
  "numOfRows","pageNo","totalCount"},"header":{"resultCode":"00",…}}}`. 코드는 문자열

## 공동주택 기본 정보 — 국토교통부 `AptBasisInfoServiceV5` (2026-10-05)

요청: `https://apis.data.go.kr/1613000/AptBasisInfoServiceV5/getAphusBassInfoV5?serviceKey={key}&kaptCode=<단지 코드>`

- `kapt_basis_<kaptCode>.json` — 가락동 단지 목록의 23개 전부. `kapt_basis_unknown.json` — 없는 코드(`A99999999`):
  정상 응답(`resultCode 00`)에 `kaptCode: null`인 항목
- 형식: JSON. 숫자는 JSON 숫자다 — **세대수 `kaptdaCnt`는 실수(`9510.0`)**, 호수 `hoCnt`는 정수. 사용승인일 `kaptUsedate`는
  `YYYYMMDD` 문자열, 지번 주소 `kaptAddr`(예: `서울특별시 송파구 가락동 479 헬리오시티아파트`, 부번이 없으면 `142-`)
- **세대수가 0.0인 단지가 있다**: `A10020074` 더샵송파루미스타(2026-05 사용승인) — `kaptdaCnt 0.0`, `hoCnt 183`. 0은 세대수로
  보이지 않는다(지어내지 않는다 — 009 FR-003)
- **대표 지번이 실거래와 다를 수 있다**: 헬리오시티의 `kaptAddr`는 가락동 **479**, 실거래 지번은 **913**(research R9-2 —
  기본 자료 2026-10-05 실측). 큰 단지는 여러 필지에 걸쳐 자료마다 대표 지번이 다르다 — 짝짓기는 지번만으로 하지 않는다

## 게이트웨이 오류

| 파일 | 받은 방법 | 내용 |
|------|-----------|------|
| `gateway_30.xml` | 가짜 키(`TESTKEY1234567890abcd`)로 상세 실거래 1회 | HTTP 403, `OpenAPI_ServiceResponse` — `returnReasonCode 30`, `SERVICE_KEY_IS_NOT_REGISTERED_ERROR` |
| `gateway_30.json` | 가짜 키로 법정동코드(`type=json`) 1회(2026-10-05, T054) | HTTP 403, **JSON** `{"OpenAPI_ServiceResponse":{"cmmMsgHeader":{…,"returnReasonCode":"30"}}}` — JSON 자료(법정동코드·단지 목록·기본 정보)는 게이트웨이 오류도 JSON으로 준다(셋 다 같은 본문) |

## 아파트 매매 실거래가 상세 자료 — 국토교통부 `RTMSDataSvcAptTradeDev` (2026-10-05, 활용신청 반영 뒤)

요청: `https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev?serviceKey={key}&LAWD_CD=<시·군·구 5자리>&DEAL_YMD=<YYYYMM>&pageNo=<쪽>&numOfRows=1000`

| 파일 | 범위 | `totalCount` | 비고 |
|------|------|--------------|------|
| `trade_11710_YYYYMM_pN.xml.gz` | 송파구 2020-01 ~ 2023-09(45개월, 46쪽) | 달마다(42 ~ 1,173) | gzip — 한 달 수백 KB라 그대로 넣지 않는다. 헬리오시티 참조값(SC-003) |
| `trade_11710_202006_p1.xml.gz`·`_p2.xml.gz` | 2020-06 | 1,173 | **2쪽짜리 달** — 1쪽 1,000행, 2쪽 173행 |
| `trade_11710_200511_p1.xml` | 2005-11 | 0 | 첫 달 탐색 — 거래 없음(정상 `000`, `items` 비어 있음) |
| `trade_11710_200512_p1.xml` | 2005-12 | 3 | 첫 달 탐색 — 처음으로 거래가 있는 달 |
| `trade_11710_202701_p1.xml` | 2027-01(미래) | 0 | 입력 오류도 정상 `000` + 0건이다(R9-1) |
| `trade_51110_202001_p1.xml.gz` | 춘천(새 코드) 2020-01 | 308 | 개편 뒤 코드로 과거 거래가 온다 |
| `trade_42110_202001_p1.xml` | 춘천(옛 코드) 2020-01 | 0 | 사라진 코드는 0건(research R9-3) |

- 형식: XML, `response/header/resultCode`(정상 `000`), `body/items/item[]`, `body/totalCount`. 빈 값은 공백 한 칸(`<aptDong> </aptDong>`)이다
- 필드: `aptSeq`(단지 일련번호 — **`11710-8865`처럼 시·군·구 코드가 들어간다** — 개편하면 바뀐다), `sggCd`·`umdCd`(5자리 —
  법정동 코드 = 둘을 붙인 10자리), `bonbun`·`bubun`(4자리 0 채움 — `0574`·`0000`), `jibun`, `aptNm`, `aptDong`, `floor`,
  `excluUseAr`(전용㎡, 소수 2자리까지), `dealAmount`(만원, 쉼표 — `"75,000"`), `dealYear`·`dealMonth`·`dealDay`, `cdealType`(해제면
  `O`), `cdealDay`(해제 신고일 `YY.MM.DD`), `dealingGbn`(중개거래·직거래, 2021-11 이전은 공백), `buildYear`, `umdNm` 등
- **헬리오시티** = `aptSeq 11710-8865`, 지번 913, 법정동 1171010700. 2020-01 ~ 2023-09 558건, 해제 27건. 이 픽스처를 이 도구의 평형
  경계·그 달 평균(반올림)으로 계산하면 사용자 스프레드시트(`helio_sheet_2020_2023.csv`)와 **해제를 넣은 계산에서 225칸 모두**
  같다(해제를 빼면 200칸 — 2026-10-05 확인, research R9-2)

## 참조값·합성 픽스처

| 파일 | 내용 |
|------|------|
| `helio_sheet_2020_2023.csv` | 사용자 스프레드시트(헬리오시티 평형별 월 거래 수·평균, 날짜 열 없음 — 2020-01부터 맞춘 45행)를 옮겨 적은 것. 열은 10평대·20평대·30평대(국평)·30평대(대형)·40평대 |
| `gateway_22.xml` | **합성** — 한도 초과(사유 22)는 실제로 받을 수 없어 `gateway_30.xml`의 코드·문구만 바꿨다(`LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR`) |
