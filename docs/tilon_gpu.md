# 교내 GPU(틸론 Tilon x KTNF) 활용 방법

## 왜 교내 GPU인가
팀플 서약이 다루는 데이터는 **학생 이름, 과제물, 평가 결과**입니다.
이를 외부 상용 API(OpenAI 등)로 보내면 개인정보·저작물 유출 우려가 있습니다.
그래서 **교내 틸론 GPU VM 에 한국어 오픈 LLM 을 직접 띄우고**, 앱의 4개 AI 단계(역할 설계·검토·판정·리포트)를 모두 그 서버에서 처리하도록 설계했습니다.
앱은 OpenAI 호환 인터페이스만 사용하므로 **코드 수정 없이 Base URL 만 바꾸면** 전환됩니다.

## 1. 틸론 GPU VM 준비
1. 교내 틸론 포털에서 GPU VM(예: NVIDIA L40S/A100, Ubuntu 22.04) 생성
2. 접속 후 드라이버 확인
   ```bash
   nvidia-smi
   ```

## 2. 모델 서빙 (둘 중 하나)

### A) vLLM — 권장 (동시 요청 처리 빠름)
```bash
pip install vllm
# 한국어 성능이 좋은 LG EXAONE 3.5 7.8B (VRAM ~16GB). 더 작은 GPU면 2.4B 사용
vllm serve LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct \
  --host 0.0.0.0 --port 8000 \
  --max-model-len 16384 \
  --served-model-name exaone
```

### B) Ollama — 가장 간단
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull exaone3.5:7.8b
OLLAMA_HOST=0.0.0.0:8000 ollama serve      # OpenAI 호환 경로: http://<IP>:8000/v1
```

## 3. 연결 확인
```bash
curl http://<틸론VM-IP>:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"exaone","messages":[{"role":"user","content":"안녕"}]}'
```

## 4. 앱에서 사용
- 사이드바 → **AI 설정** → LLM 제공자: `틸론 GPU 서버 (vLLM/Ollama · OpenAI 호환)`
- Base URL: `http://<틸론VM-IP>:8000/v1`
- 모델: `exaone` (vLLM `--served-model-name`) 또는 `exaone3.5:7.8b` (Ollama)
- API Key: `EMPTY`
- **연결 테스트** 버튼으로 확인

배포 환경(Streamlit Cloud)에서는 Secrets 에 다음을 넣으면 시작부터 틸론 서버를 사용합니다.
```toml
TILON_API_KEY = "EMPTY"
TILON_BASE_URL = "http://<틸론VM-IP>:8000/v1"
```
(교내망 전용 IP라면 외부 배포 서버에서는 접근이 안 될 수 있으므로, 시연 시 교내 PC에서 `streamlit run app.py` 로 실행하거나 포트포워딩/터널을 사용합니다.)

## 5. 틸론 GPU 에서 수행한/수행할 작업
| 작업 | 설명 | GPU 활용 |
|---|---|---|
| 4단계 AI 추론 서빙 | 역할 설계 · 검토 · 판정 · 리포트 프롬프트를 EXAONE 으로 처리 | vLLM 추론 |
| 프롬프트 회귀 테스트 | `PROMPT_LOG.md` 의 테스트 케이스(형식적 제출 vs 실제 작업물)를 로컬 모델로 반복 실행해 판정 일관성 점검 | 배치 추론 |
| (확장) 판정 AI 미세조정 | 학기 동안 쌓인 (제출물, 판정) 쌍으로 LoRA 미세조정 → 과목별 기준 반영 | 학습 |

## 6. 비용·성능 메모
- EXAONE-3.5-7.8B, L40S 기준 제출물 1건 검토+판정 ≈ 3~6초, 외부 API 비용 0원
- 동일 코드로 외부 API 와 A/B 비교 가능 → 「프롬프트 기록」 탭에 모델명·응답시간이 함께 저장됨
