# HomeTax Automation with Pydoll

이 프로젝트는 기존의 Selenium 기반 홈택스 자동화 스크립트를 Pydoll로 변환한 버전입니다.

## 주요 변경사항

### 1. 라이브러리 변경
- **이전**: Selenium WebDriver + PyInquirer
- **이후**: Pydoll (Chrome 기반 브라우저 자동화) + 내장 input() 함수

### 2. 코드 패턴 변경
- **동기식 → 비동기식**: 모든 함수가 `async/await` 패턴으로 변경
- **브라우저 초기화**: `webdriver.Chrome()` → `async with Chrome() as browser:`
- **탭 관리**: `browser` → `tab = await browser.start()`
- **요소 찾기**: `find_element_by_*()` → `await tab.find()`
- **요소 상호작용**: `element.click()` → `await element.click()`

### 3. 주요 메서드 변환
| Selenium | Pydoll |
|----------|--------|
| `browser.get(url)` | `await tab.go_to(url)` |
| `browser.find_element_by_id(id)` | `await tab.find(id=id)` |
| `browser.find_elements_by_xpath(xpath)` | `await tab.find_all(xpath=xpath)` |
| `element.click()` | `await element.click()` |
| `element.text` | `await element.text` |
| `element.is_enabled()` | `await element.get_attribute("disabled")` |
| `browser.switch_to_frame(iframe)` | `tab = await tab.get_frame(iframe)` |
| `time.sleep(n)` | `await asyncio.sleep(n)` |

### 4. 설치 및 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# 스크립트 실행
python3 hometax_pydoll.py
```

## 주의사항

1. **비동기 실행**: 모든 브라우저 상호작용이 비동기로 처리됩니다.
2. **알림 처리**: Selenium의 alert 처리 방식과 다르게 구현되었습니다.
3. **iframe 처리**: `get_frame()` 메서드를 사용하여 iframe 컨텍스트를 변경합니다.
4. **요소 활성화 확인**: `is_enabled()` 대신 `get_attribute("disabled")` 사용
5. **메뉴 시스템**: PyInquirer 대신 내장 `input()` 함수 사용 (Python 3.12 호환성 문제 해결)

## 장점

- **더 빠른 실행**: Pydoll은 WebDriver 없이 직접 Chrome과 통신
- **더 안정적**: 브라우저 감지 회피 기능 내장
- **더 현실적인 상호작용**: 실제 사용자와 유사한 동작 패턴
