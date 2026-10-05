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

## 아직 받지 못한 것

- **상세 실거래(`RTMSDataSvcAptTradeDev`)** — 2026-10-05 현재 이 키에 등록되지 않았다(실제 키로도 403, 사유 30). 등록이 반영되면
  송파구 2020-01~2023-09 전체 쪽(gzip), 2쪽 이상인 달, 첫 달 탐색(2005-11·12), 미래 달, 춘천 새·옛 코드(51110·42110)를 받는다
- 한도 초과(사유 22)는 실제로 받을 수 없다 — `gateway_30.xml`의 코드·문구만 바꾼 합성 픽스처로 둔다(받을 때 함께 만든다)
