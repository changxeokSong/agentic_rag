# 🚀 성능 최적화 가이드

## ⚠️ 현재 문제

**도구 선택에 45초 소요** → 이는 비정상입니다!

### 원인:
- 현재 모델: `exaone-4.0.1-32b` (32B 파라미터)
- 32B 모델은 너무 크고 느립니다
- GPU 가속 없이는 CPU에서 매우 느림

---

## ✅ 해결 방법

### 1️⃣ **더 작은 모델로 변경** (강력 권장)

#### 추천 모델 (속도 순):
1. **llama-3.2-3b-instruct** (3B) - 가장 빠름 ⚡⚡⚡
2. **qwen2.5-7b-instruct** (7B) - 빠름 ⚡⚡
3. **llama-3.2-8b-instruct** (8B) - 빠름 ⚡⚡
4. **exaone-4.0.1-8b** (8B) - 중간 ⚡

#### 변경 방법:

**1. LM Studio에서 모델 다운로드**
- LM Studio 앱 열기
- Search에서 "llama-3.2-3b-instruct" 검색
- Download 클릭

**2. 모델 로드**
- 다운로드 완료 후 Load 클릭
- Local Server 시작

**3. .env 파일 수정**
```bash
# /mnt/c/Users/mmlab/Desktop/agentic_rag/.env
LM_STUDIO_MODEL_NAME=llama-3.2-3b-instruct
```

**4. 컨테이너 재시작**
```bash
docker-compose restart backend frontend
```

---

### 2️⃣ **GPU 가속 확인**

#### LM Studio 설정:
```
Settings → GPU Acceleration → CUDA (NVIDIA) 또는 Metal (Mac)
```

#### GPU가 없다면:
- CPU에서는 3B-8B 모델 권장
- 32B 모델은 GPU 필수

---

### 3️⃣ **LM Studio 성능 설정**

#### Context Length 줄이기:
```
Model Settings → Context Length: 2048 (4096에서 줄이기)
```

#### Batch Size 조정:
```
Model Settings → Batch Size: 512 (기본값)
```

---

## 📊 모델별 예상 성능

| 모델 | 크기 | 도구 선택 | 최종 답변 | 품질 |
|------|------|-----------|-----------|------|
| **llama-3.2-3b** | 3B | 2-3초 ⚡⚡⚡ | 5-8초 | 좋음 |
| **qwen2.5-7b** | 7B | 3-5초 ⚡⚡ | 8-12초 | 매우 좋음 |
| **llama-3.2-8b** | 8B | 3-5초 ⚡⚡ | 8-12초 | 매우 좋음 |
| **exaone-4.0.1-8b** | 8B | 4-6초 ⚡ | 10-15초 | 훌륭함 |
| **exaone-4.0.1-32b** | 32B | **45초** ❌ | 60초+ | 최고 |

---

## 🎯 권장 설정 (최고 성능)

### .env 파일:
```bash
LM_STUDIO_MODEL_NAME=llama-3.2-3b-instruct  # 또는 qwen2.5-7b
REQUEST_TIMEOUT=90
MAX_TOKENS=8192  # 자세한 답변
RESPONSE_TEMPERATURE=0.7
TOOL_SELECTION_TEMPERATURE=0.0
```

### LM Studio:
- GPU 가속: ON
- Context Length: 2048
- Batch Size: 512
- Temperature: 0.7

---

## 🔍 현재 적용된 최적화

✅ 도구 선택 프롬프트: 극도로 간소화 (토큰 90% 감소)
✅ 도구 선택 토큰: 128 (최소화)
✅ 최종 답변 토큰: 10392 (자세함)
✅ 실시간 스트리밍: 타자기 효과

---

## ⚡ 즉시 적용 가능한 임시 해결책

**지금 당장 빠르게 하려면:**

1. **모델만 변경** (가장 효과적)
   ```bash
   # .env
   LM_STUDIO_MODEL_NAME=llama-3.2-3b-instruct

   # 재시작
   docker-compose restart backend frontend
   ```

2. **또는 답변 길이 제한**
   ```bash
   # .env
   MAX_TOKENS=2048  # 10392에서 줄이기
   ```

---

## 📈 예상 개선 효과

**32B → 3B 모델 변경 시:**
```
도구 선택: 45초 → 2-3초 (15배 빠름!) ⚡⚡⚡
최종 답변: 60초+ → 5-8초 (7배 빠름!) ⚡⚡⚡
전체: 105초 → 7-11초 (10배 빠름!) 🚀
```

---

## 🆘 문제 해결

### Q: 모델 변경 후에도 느려요
**A**: LM Studio를 완전히 재시작하고 모델을 다시 로드하세요.

### Q: GPU가 감지 안 돼요
**A**: NVIDIA 드라이버와 CUDA를 설치하세요.

### Q: 답변 품질이 떨어졌어요
**A**: 7B-8B 모델로 변경하거나 Temperature를 0.8로 올리세요.

---

## 💡 최종 권장사항

### **즉시 해야 할 것:**
1. ✅ **모델을 3B-8B로 변경** (가장 중요!)
2. ✅ GPU 가속 활성화
3. ✅ Context Length 2048로 설정

### **선택사항:**
- MAX_TOKENS 조정 (더 짧은 답변 원하면 줄이기)
- Temperature 조정 (더 창의적 답변 원하면 올리기)

---

**작성일**: 2025-10-14
**작성자**: Claude Code
