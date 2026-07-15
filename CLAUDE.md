# CLAUDE.md

이 파일은 이 저장소에서 작업할 때 Claude Code(claude.ai/code)에게 제공하는 가이드입니다.

## 이 저장소는 무엇인가

바샤커피(Bacha Coffee) 원두 라인업을 소개하는 정적인 개인 운영 마케팅/참고용 사이트(한국어, `lang="ko"`)입니다. 바샤커피와는 아무런 제휴 관계가 없습니다(모든 상세 페이지 하단의 비공식 안내 문구 참고). 빌드 단계, 패키지 매니저, 테스트가 전혀 없는 순수 HTML/CSS/JS 사이트이며 `https://youngsic1236.github.io/bacha-coffee-guide-/` 로 GitHub Pages를 통해 배포됩니다.

## 개발 워크플로우

이 저장소에는 빌드/린트/테스트 도구가 없습니다(`package.json` 없음, CI 설정 없음). 개발 방식은 다음과 같습니다:

- HTML 파일을 직접 수정한다.
- 브라우저에서 `index.html`을 직접 열거나, 상대경로(`coffee/...`, `images/...`)가 정상 동작하도록 디렉터리를 로컬 서버로 띄워서(`python3 -m http.server` 등) 미리 본다.
- 커밋 후 푸시하면 GitHub Pages가 저장소에서 바로 서빙한다.

시각적/상호작용 요소를 수정했다면 실제로 브라우저에서 열어 필터, 검색, 퀴즈, 모달 등을 직접 클릭해 확인해야 합니다 — 회귀를 잡아줄 자동 테스트가 없습니다.

## 구조

- `index.html` — 홈페이지 전체: 인라인 `<style>`, 46개 원두의 `<article class="card">` 전체, 그리고 모든 상호작용 기능을 구현하는 인라인 `<script>` 블록까지 한 파일에 들어 있습니다. 약 2,600줄짜리 단일 파일이며 대부분의 작업이 여기서 이루어집니다.
- `coffee/*.html` — 원두별 정적 상세 페이지(46개 파일, `index.html`의 카드 46개와 1:1 대응). 각각 자체 인라인 스타일과 JSON-LD 구조화 데이터를 가진 독립적인 페이지이며, 각 카드에서 `coffee/<slug>.html`로 연결됩니다.
- `images/` — 제품 사진. 제품 카테고리와 동일한 이름의 하위 폴더로 정리되어 있습니다(`single origin/`, `Decaffeinated/`, `Nomad WB/`, `Fine Flavoured Coffee Drip bag (12p)/`, `Drip Bag Gift Box/`). 폴더/파일명에 공백이 포함되어 있고, 상대경로가 아니라 `%20`으로 인코딩된 raw-GitHub 전체 URL(`https://raw.githubusercontent.com/youngsic1236/bacha-coffee-guide-/main/images/...`)로 참조합니다 — 이는 Open Graph/소셜 카드 스크래퍼가 페이지 상대경로를 해석하지 못하기 때문에 의도적으로 절대경로를 쓰는 것입니다.
- `sitemap.xml`, `robots.txt` — SEO 관련 파일. `sitemap.xml`은 `coffee/*.html` URL을 전부 나열하므로 `coffee/` 디렉터리와 항상 동기화되어야 합니다.

## 원두 데이터가 세 곳에 중복되어 있다는 점 (가장 중요한 함정)

원두 하나의 데이터는 **서로 독립된 세 곳**에 존재하며, 원두를 추가/삭제/수정할 때마다 수동으로 동기화해야 합니다:

1. `index.html`의 `<article class="card" data-cat="..." data-acidity="..." data-strength="...">` 블록 (이름, 원산지, 로스팅 배지, 풍미 태그, 설명, 강도/산미 미터, 이미지 URL, 상세 페이지 링크).
2. 해당 `coffee/<slug>.html` 상세 페이지 (동일 정보를 JSON-LD `additionalProperty` 메타데이터와 함께 전체 페이지로 재기술).
3. `index.html` 내 인라인 `QUIZ_DATA` JS 배열 (퀴즈 문제 생성에 쓰이는 `{kr, en, origin, flag, tags, acidity, cat}` 형태의 JSON 유사 배열).

여기에 더해 새 상세 페이지를 만들면 `sitemap.xml`에도 `<url>` 항목을 추가해야 합니다. 공용 데이터 소스나 생성 스크립트가 없으므로, 원두 데이터 수정은 `index.html`의 카드, `index.html`의 `QUIZ_DATA` 항목, 대응하는 `coffee/*.html` 파일, `sitemap.xml`까지 4곳을 함께 바꿔야 하는 작업으로 취급하세요.

## `index.html` 아키텍처 (홈페이지)

모든 로직은 인라인 `<script>` 태그 안에 전역 함수/변수 방식으로 비교적 선형적으로 작성되어 있습니다(프레임워크·모듈 없음). 등장 순서대로 주요 부분은 다음과 같습니다:

- **Supabase 기반 퀴즈 리더보드**: `SUPA_URL`/`SUPA_KEY`(anon key로, Supabase의 클라이언트 사이드 모델상 공개되어도 되는 키)가 `quiz_rankings` 테이블을 REST로 직접 호출합니다(`submitRanking`, `loadLeaderboard`). 점수 집계/평균 계산은 클라이언트에서 이루어집니다.
- **필터 바 + 검색** (`applyFilters`, `isNaturalLanguageQuery`, `parseTextInput`): 카드는 카테고리(`data-cat`), 산미(`data-acidity`), 강도(`data-strength`) 칩으로 필터링되며, 자유 텍스트 검색창은 자연어 선호 문장("산미", "고소", "진한" 같은 한국어 신호어)도 필터 조건으로 파싱을 시도합니다.
- **추천 플로우** (`toggleRecommend`, `rec-*` 요소들): 짧은 선택형 질문으로 사용자 답변에 맞춰 카드에 점수를 매겨 상위 매칭 결과를 보여줍니다.
- **트리비아 퀴즈** (`startQuiz`, `renderQuizQuestion`, `renderMatchQuestion`, `QUIZ_DATA`): `QUIZ_DATA`로부터 객관식/짝맞추기 등 여러 유형의 문제를 생성하며, 결과는 위의 Supabase 리더보드로 이어집니다.
- **상세 모달** (`#detail-modal-overlay`, `closeDetailModal`): 카드를 클릭하면 스토리/향·풍미/페어링/리뷰 섹션이 있는 인페이지 모달이 열리며, 클릭한 카드의 DOM과 추가로 내장된 콘텐츠로 채워집니다 — `coffee/*.html` 페이지로 이동하는 것의 대안입니다.
- **가격 태그** (`renderPriceTags`, `getPriceInfo`, `PRICE_BY_CAT`, `PREMIUM_NAMES`): 가격은 카드마다 저장되어 있지 않고, 렌더링 시점에 카테고리와 하드코딩된 프리미엄 이름 목록으로부터 계산됩니다.

## 원두를 추가할 때 지킬 규칙

- `data-cat`은 기존 값 중 하나를 사용합니다: `single`, `flavoured`, `decaf`, `wb`(홀빈), `gift`.
- 각 카드의 `data-search`는 검색창이 사용하는, 사람이 직접 관리하는 공백 구분 한글/영문 키워드 모음입니다(이름, 원산지, 풍미 노트) — 새 카드에도 반드시 채워 넣으세요.
- 상세 페이지 파일명은 케밥 케이스 영문 슬러그입니다(예: `sidamo-mountain.html`). 기존 원두의 홀빈 버전은 새 슬러그가 아니라 `-wb` 접미사를 붙입니다(예: `blue-danube-wb.html`).
- 새 `coffee/*.html`을 만들 때는 다른 파일들의 메타 태그/Open Graph/JSON-LD 상용구를 그대로 따르세요 — canonical URL, `og:*`, `twitter:*`, 브레드크럼 `application/ld+json` 블록 모두 동일한 템플릿을 사용합니다.
- 모든 상세 페이지는 비제휴 안내 문구 `<div class="notice">`로 끝납니다 — 새 페이지에도 반드시 유지하세요.
