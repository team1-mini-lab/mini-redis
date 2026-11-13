# Battery RUL Dashboard: Few-Shot Bayesian Meta-Learning with Live Inference

**🎯 목표**: TensorFlow/PyTorch 기반 딥러닝 프레임워크를 활용한 AI 추론 시스템 개발. 초기 짧은 데이터(Support Set)만으로 배터리 잔여수명(RUL) 예측 및 실시간 재추론

**🔗 Live Demo**: https://onekindalpha-battery-rul-dashboard-bmaml-svgd.hf.space

---

## 📊 프로젝트 개요

이 프로젝트는 **풀스택 AI/ML 엔지니어링 구현**입니다 (Feature Engineering → 딥러닝 모델 → 추론 배포):

- **데이터 전처리**: NASA 배터리 데이터 → Feature Engineering (40 시계열 특성) → Few-shot Task 구성
- **딥러닝 아키텍처**: BMAML-SVGD 메타러닝 + CEEMDAN-Transformer-DNN 백본
- **프로덕션 추론**: PyTorch 모델 → Precomputed 캐시 + Live Inference → Docker + HF Spaces
- **풀스택 구현**: React/Vite 대시보드 + FastAPI 백엔드 (총 6,700+ 줄 코드)

---

## 🔴 핵심 기술

### 1️⃣ 데이터 엔지니어링 (Data Pipeline)

#### 특성 엔지니어링
```
Raw Battery Data (Voltage, Current, Temperature, Capacity, Impedance)
    ↓
Time-series Features (40 차원)
  - Capacity degradation velocity
  - DCR/Impedance growth rate  
  - Temperature stress indicators
  - Current/load stress metrics
  - CEEMDAN-based IMF decomposition
  - LLI/LAM proxy signals
    ↓
3D 스케일링 (시간 × 배터리 × 특성)
  - CustomRobustScaler3D (p=90 percentile)
  - 이상치 robust 처리
  - Per-battery normalization
    ↓
Few-Shot Task 구성 (Support + Query)
```

**파일**: `deep_learning/core/train_meta.py` (651줄)
- `fit_scalers()`: 90-percentile robust scaler 학습
- `MetaBatteryDataset`: Task-level 샘플링 (support k-shot, query q-query)
- Data augmentation: Task 균형 관리

#### Few-Shot 설정
```python
Support Set: 16 cycles (초기 관측 기간)
Query Set: 16 cycles (미래 예측 구간)
Batch Size: 2 tasks/batch
Meta-Train Batteries: 14개 (B0005-B0053 subset)
Meta-Val Batteries: 2개
Meta-Test Batteries: 6개
```

### 2️⃣ 딥러닝 아키텍처 (Few-Shot Bayesian Meta-Learning 기반 시퀀스 모델)

#### BMAML-SVGD (Bayesian Model-Agnostic Meta-Learning with Stein Variational Gradient Descent)

```
Input: (seq: [T×D], sum: [S])  where T=시간, D=특성수, S=summary차원

Backbone: CEEMDAN-Transformer-DNN
├─ CEEMDAN decomposition: 시계열 → IMF components
├─ Transformer encoder: 장기 의존성 학습
└─ DNN head: RUL 예측

Meta-Learning Loop:
├─ Inner loop (Task adaptation):
│   └─ Few-step gradient descent: support set으로 task-specific adaptation
├─ Outer loop (Meta update):
│   └─ BMAML: 모든 task의 gradient 합산
└─ SVGD: 파라미터 입자(U=3)로부터 다중 예측값 생성 → 예측 분포 근사
```

**파일**: 
- `deep_learning/core/models.py`: MultiTaskRULModel 아키텍처
- `deep_learning/core/meta_utils.py`: `bmaml_inner()` - inner loop 구현
- `deep_learning/core/bmaml_runtime.py`: Inference 엔트리포인트

#### 성능 지표 (Training Results)

| 지표 | 값 | 설명 |
|-----|-----|------|
| **RMSE** | **7.46 cycles** | Query set 예측 오차 (r_ratio=0.20 기준) |
| **MAE** | **6.82 cycles** | Mean absolute error |

---

## 🏗️ 아키텍처 (End-to-End)

### Data Flow

```
Raw Data (NASA Cycle Dataset)
    ↓
[Data Engineering]
    - CSV → Parquet (메모리 효율)
    - Feature engineering (40 dimensions)
    - 3D normalization (seq_scaler, sum_scaler)
    ↓
[Model Training] (Ray Tune + ASHA)
    - Task sampling (support: 16, query: 16)
    - BMAML meta-learning (5-way inner loop)
    - SVGD Bayesian uncertainty
    - Checkpoint: nasa_bmaml_best_re.pt (20MB)
    ↓
[Precomputed Cache] (배포 최적화)
    - Prediction for r_ratio ∈ [0.1, 0.2, 0.3, 0.4]
    - JSON format: {battery, r_ratio, payload: {query, pred, support, metrics}}
    - Total: ~200 JSON files (2-5MB 각)
    ↓
[Live Inference Engine]
    - POST /api/battery/{id}/reinfer?r_ratio=X
    - Runtime: ~40초 (CPU-only, HF Spaces)
    - Output: {pred, std, confidence, metrics}
    ↓
[FastAPI Backend]
    - DuckDB for tabular data access (2M+ rows)
    - Anomaly detection (degradation monitoring)
    - Precomputed fallback (API 404 → JSON 파일)
    ↓
[React Frontend]
    - Overview: RUL curve + uncertainty band
    - Degradation: Capacity, DCR, Impedance, Temperature monitoring
    - Explainability: SHAP global importance + confidence
    - Live Reinference: Button → backend call → state update
    ↓
[Docker Deployment]
    - Python 3.10-slim + npm
    - Frontend build: Vite (6.2MB bundled)
    - Backend: uvicorn (timeout 900s for inference)
    - Hugging Face Spaces (CPU-only, 16GB RAM)
```

---

## 📁 프로젝트 구조

```
battery-rul-dashboard/
├─ deep_learning/
│  └─ core/
│     ├─ train_meta.py           # BMAML 메타 학습 (651줄)
│     ├─ models.py               # CEEMDAN-Transformer-DNN 백본
│     ├─ meta_utils.py           # Inner loop, SVGD utilities
│     ├─ bmaml_runtime.py        # Inference 엔트리
│     ├─ feature_shap_bmaml.py   # SHAP interpretability
│     └─ config.py               # Hyperparameters
│
├─ backend/
│  └─ app/
│     ├─ main.py                 # FastAPI (3,126줄)
│     │  ├─ /api/battery/{id}/precomputed      # Precomputed data
│     │  ├─ /api/battery/{id}/reinfer          # Live inference
│     │  ├─ /api/battery/{id}/degradation-monitoring  # Anomaly
│     │  └─ /api/fixed4/shap-current           # Feature importance
│     ├─ data_access.py          # DuckDB queries
│     ├─ settings.py             # Config (동적 경로)
│     └─ diagnostics.py          # Anomaly detection logic
│
├─ frontend/
│  └─ src/
│     └─ ui/
│        ├─ App.tsx              # Main dashboard (2,844줄)
│        │  ├─ Overview tab      # RUL curve + metrics
│        │  ├─ Degradation tab   # Signal monitoring
│        │  ├─ Compare tab       # Multi-battery comparison
│        │  ├─ Explainability    # Uncertainty + SHAP
│        │  └─ Live reinference  # Button + result state
│        └─ ExplainabilityAnomalyV30.tsx  # 상세 분석
│
├─ data/
│  ├─ nasa_features_rul.csv      # 원본 특성 (1.3MB)
│  ├─ precomputed/               # 캐시된 예측 (r-ratio별)
│  └─ precomputed_from_export_v2/
│
├─ scripts/
│  ├─ prefix_inference_viz_meta_restored_v3.py   # Inference runner
│  └─ [다른 유틸리티들]
│
├─ core_checkpoints/
│  └─ nasa_bmaml_best_re.pt      # 최종 모델 (Git LFS, 20MB)
│
├─ Dockerfile                     # Multi-stage build
├─ hf_app.py                      # FastAPI + React serving
├─ run_bmaml_reinfer.py           # Reinference wrapper
└─ README.md
```

---

## 🚀 주요 기능

### 1. Overview Tab
- **RUL Prediction Curve**: Support 기간 → Query 기간의 예측 궤적
- **Uncertainty Band**: ±2σ confidence interval
- **Metrics**: RMSE, MAE, Confidence % 실시간 계산

### 2. Degradation Monitoring
- **6개 신호**: Capacity, DCR, Impedance, Temperature, Current stress, LLI proxy
- **Anomaly Detection**: Z-score 기반 이상치 플래깅
- **Cycle-level Evidence**: 각 cycle에서 degradation signal 요약

### 3. Explainability
- **Prediction Variance**: SVGD 다중 입자로부터 생성된 예측값 분포
- **Global Feature Importance**: SHAP 기반 top-12 features
- **Cumulative Anomaly Report**: Support → Query 기간의 이상신호 누적

### 4. Live Reinference
- **버튼**: `Initialize & Reinference`
- **Runtime**: ~40초 (CPU, HF Spaces)
- **Output**: 새로운 (pred, std, confidence, metrics)
- **Session State**: React state에 반영, CSV log 저장

---

## 🔧 기술 스택

| 분야 | 기술 |
|------|------|
| **Deep Learning Framework** | PyTorch 2.0, TensorFlow (경험) |
| **Few-Shot Bayesian Meta-Learning** | BMAML (Bayesian Model-Agnostic Meta-Learning) + SVGD |
| **Posterior Approximation** | SVGD (Stein Variational Gradient Descent) |
| **Backbone Network** | CEEMDAN + Transformer + DNN |
| **Signal Processing** | CEEMDAN, RobustScaler (90-percentile) |
| **Feature Engineering** | 40 time-series features |
| **Hyperparameter Tuning** | Ray Tune + ASHA scheduler |
| **Backend** | FastAPI, DuckDB (2M+ rows) |
| **Frontend** | React, Vite, TailwindCSS, Plotly.js |
| **Deployment** | Docker, Hugging Face Spaces, Git LFS |
| **Experiment Tracking** | Weights & Biases (optional) |

---

## 📈 성능 및 확장성

### 벤치마크

```
Dataset: NASA Battery (6,000+ cycles/battery, 14+ batteries)
Training: 8-12시간 (1× RTX3090, ASHA 조기중단)
Final Performance: RMSE 7.46 cycles, MAE 6.82 cycles (r_ratio=0.20)
Inference: ~40초 per battery (CPU, support+query 예측)
Precomputed Cache: ~200MB (r_ratio 4가지, /data/precomputed_from_export_v2/)
```

### 확장성 고려사항

| 항목 | 현재 | 향후 |
|------|------|------|
| **Dataset** | NASA only | + CALCE, EV6 real-world |
| **Batch Size** | 2 tasks | → 4-8 (memory scaling) |
| **Particles** | M=3 (SVGD) | → M=5-10 (accuracy) |
| **Feature Dim** | 40 | → 60+ (signal enrichment) |
| **Deployment** | CPU (HF Spaces) | → GPU instance (cloud) |
| **Model Size** | 2.3MB | → Quantization (1.5MB) |

---

## 💡 설계 철학

### 1. Few-Shot Generalization
- **왜**: 실제 운용 환경에서는 배터리 초기 데이터만 사용 가능
- **어떻게**: Support set (16 cycles) → Task-specific adaptation (inner loop) → Query set (16 cycles) 예측
- **결과**: 미래 구간 예측 가능

### 2. Ensemble Prediction via SVGD
- **왜**: 단일 예측값보다 다중 예측으로 모델 불확실성 파악
- **어떻게**: SVGD로 훈련된 3개의 파라미터 입자로부터 3개 예측값 생성
- **결과**: 예측값의 분산으로 모델 신뢰도 평가

### 3. Production-Ready Inference
- **Precomputed Cache**: 빠른 초기 로딩 (JSON 조회, <100ms)
- **Live Reinference**: 정교한 분석 필요 시 on-demand 추론 (~40초)
- **API Fallback**: 백엔드 404 → JSON 파일 fallback (배포 안정성)

### 4. Full-Stack Observability
- **DuckDB**: 구조화된 데이터 빠른 쿼리
- **SHAP**: 모델 해석 가능성 (feature importance)
- **Anomaly Report**: Cycle-level degradation evidence

---

## 🛠️ 로컬 개발

### 환경 설정

```bash
# 1. 환경 생성
conda create -n battery-maml python=3.10
conda activate battery-maml

# 2. 백엔드 설치
pip install -e ./backend

# 3. ML 의존성
pip install torch==2.2.2 torchvision==0.17.2 torchaudio==2.2.2
pip install ray[tune]==2.20.0
pip install pyyaml

# 4. 프론트엔드
cd frontend && npm install && npm run dev
```

### 모델 학습

```bash
cd deep_learning/core
python train_meta.py --config config.yaml \
  --k_shot 30 --q_query 128 --meta_lr 0.001 --inner_lr 0.01
```

### Live Inference (로컬)

```bash
python run_bmaml_reinfer.py \
  --battery B0043 \
  --checkpoint ../core_checkpoints/nasa_bmaml_best_re.pt \
  --r_ratio 0.2
```

---

## 🚢 배포 (Hugging Face Spaces)

### Git 푸시

```bash
# GitHub
git push origin main

# Hugging Face (자동 Docker build)
git push hf main
```

### Dockerfile 포인트

- **Multi-stage**: pip install + npm build 병렬화
- **경로 동적화**: `/app/data` (Docker) vs 로컬 경로 자동 감지
- **Git LFS**: checkpoint (20MB) Git LFS로 추적
- **Timeout**: 900초 (live reinference 완료용)

---

## 🔍 관련 논문 & 영감

- **MAML** (Finn et al., 2017): Model-Agnostic Meta-Learning
- **BMAML**: Bayesian MAML (불확실성)
- **SVGD** (Liu & Wang, 2016): Stein Variational Gradient Descent
- **CEEMDAN** (Torres et al., 2011): Signal decomposition

---

## 📝 라이센스

MIT License

---

## 👤 저자

**Velocitygoal** - Full-stack AI/Data Engineer
- 데이터 파이프라인: Feature engineering, Few-shot task 구성, 3D normalization
- ML 모델: BMAML-SVGD 구현, CEEMDAN backbone, uncertainty 추정
- 백엔드: FastAPI, DuckDB, anomaly detection
- 프론트엔드: React, 실시간 상태 관리, 대시보드 UI/UX
- 배포: Docker, HF Spaces, Git LFS

---

## 📞 문의

- **Live Demo**: https://onekindalpha-battery-rul-dashboard-bmaml-svgd.hf.space
- **GitHub**: [repository link]
- **Questions**: 이슈 또는 discussions 남겨주세요
