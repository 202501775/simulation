"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NOVA시 스마트시티 자원 배분 시뮬레이터 v2.0
classes.py — 전체 클래스 정의

[설계 철학]
이 프로젝트는 세 가지 스마트시티 정의의 간극을 다룬다.
  ① 한국 정부: 기술 구현 중심
  ② IMD: 시민 체감 삶의 질 중심
  ③ 이 프로젝트: 자원 배분의 형평성 중심

핵심 메시지:
"예산의 총량이 아니라 배분의 방향이 시민의 삶을 결정한다.
 에너지의 규모가 아니라 에너지원의 구성이 도시의 지속가능성을 결정한다."

[v2 수정사항]
- 초기 에너지 자립률 상향 (E구역 제외 40% 이상 진입)
- 구역별 시민 구성 비율 현실 범위 내 극단화
- 에너지 패널티 강도 조정 (복지집중 시나리오 희석 문제 해결)
- 전 클래스 한국어 주석 완비
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import math
from typing import Dict, List, Tuple


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [섹션 1] 커스텀 예외 클래스
# 강의안 필수 요건: 사용자 정의 예외 최소 1개 이상
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BudgetAllocationError(Exception):
    """
    [예외 1] 예산 배분 합계 오류
    
    발생 조건: 5개 예산 항목의 합계가 100%가 아닐 때
    의의: 잘못된 입력이 시뮬레이션 전체를 오염시키는 것을 방지
    
    사용 예시:
        Resource(welfare=0.30, education=0.30, ...) → 합계 110% → 이 예외 발생
    """
    def __str__(self):
        return (f"[예산 오류] 예산 배분의 합계는 반드시 100%여야 합니다. "
                f"현재 입력값 합계: {self.args[0]:.1f}%")


class LowSatisfactionWarning(Exception):
    """
    [예외 2] 위험 구역 만족도 경보
    
    발생 조건: 특정 구역의 시민 만족도가 임계치(50점) 이하일 때
    의의: 정책 실패 구역을 자동으로 감지하여 의사결정자에게 경고
    
    현실 근거:
        IMD Smart City Index에서 만족도 하위 20%에 해당하는 도시들은
        시민 이탈, 투자 감소, 사회 불안 등 복합 문제를 겪는다.
        50점 임계치는 이 하위 구간 진입 기준을 모델에 반영한 값이다.
    """
    def __str__(self):
        return (f"[위험 경보] {self.args[0]} 구역 만족도 "
                f"{self.args[1]:.1f}점 — 정책 개입 필요")


class EnergyAllocationError(Exception):
    """
    [예외 3] 에너지 배분 합계 오류
    
    발생 조건: 4개 에너지원 비율의 합계가 100%가 아닐 때
    의의: BudgetAllocationError와 동일한 방어적 설계 원칙 적용
    """
    def __str__(self):
        return (f"[에너지 오류] 에너지 배분의 합계는 반드시 100%여야 합니다. "
                f"현재 입력값 합계: {self.args[0]:.1f}%")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [섹션 2] 핵심 변환 함수
# 비선형 모델링으로 현실의 "임계점"과 "한계효용 체감" 표현
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def budget_to_fulfillment(budget_ratio: float,
                          threshold: float = 0.20) -> float:
    """
    [핵심 함수 1] 예산 비율 → 니즈 충족도 변환 (비선형)

    [이론적 근거]
    기존 선형 모델(예산 2배 = 효과 2배)은 현실을 반영하지 못한다.
    공공경제학의 두 가지 원리를 수식으로 구현했다:

    1. 공공재 임계점 이론 (Threshold Effect):
       최소 투자 기준선 미달 시 서비스 자체가 붕괴한다.
       예: 병원 예산을 절반으로 줄이면 운영이 불가능해진다.
       → threshold(20%) 이하 구간에서 급락 표현

    2. 한계효용 체감 법칙 (Diminishing Marginal Utility):
       투자를 계속 늘려도 추가 효과는 점점 줄어든다.
       예: 복지 예산 40%→50%는 20%→30%만큼 효과적이지 않다.
       → threshold*2 초과 구간에서 로그함수로 완만한 증가 표현

    [구간별 동작]
    ┌──────────────────────────────────────────────────┐
    │ 0 ~ threshold/2 : 급락 구간  →  0 ~ 40점        │
    │ threshold/2 ~ t  : 부족 구간  → 40 ~ 60점        │
    │ threshold ~ t*2  : 적정 구간  → 60 ~ 90점 ★최대효율│
    │ t*2 이상         : 체감 구간  → 90점 + 로그 완만증가│
    └──────────────────────────────────────────────────┘

    Args:
        budget_ratio: 해당 니즈에 도달하는 예산 비율 (0.0 ~ 1.0)
        threshold:    최소 적정 예산 비율 (기본값 0.20 = 20%)
                      4개 항목 균등 배분 기준값

    Returns:
        니즈 충족도 점수 (0.0 ~ 100.0)
    """
    half = threshold * 0.5  # 임계점의 절반 = 서비스 붕괴 경계

    if budget_ratio <= 0.0:
        # 예산 0: 서비스 완전 붕괴
        return 0.0

    elif budget_ratio < half:
        # 급락 구간: 기본 수요조차 충족 불가
        # 선형 보간으로 0점 → 40점
        return (budget_ratio / half) * 40.0

    elif budget_ratio < threshold:
        # 부족 구간: 최소 수요는 충족하나 부족
        # 40점 → 60점 (임계점 직전 완만한 상승)
        progress = (budget_ratio - half) / half
        return 40.0 + progress * 20.0

    elif budget_ratio < threshold * 2.0:
        # 적정 구간: 가장 효율적인 투자 구간
        # 60점 → 90점 (예산 1%p 추가 시 만족도 약 1.5점 상승)
        progress = (budget_ratio - threshold) / threshold
        return 60.0 + progress * 30.0

    else:
        # 한계효용 체감 구간: 과잉 투자
        # 로그함수로 90점 이상 완만하게 증가
        # 수식: 90 + log(초과비율 + 1) * 8
        excess = budget_ratio / (threshold * 2.0)
        return min(100.0, 90.0 + math.log(excess + 1.0) * 8.0)


def energy_to_bonus(rate: float) -> float:
    """
    [핵심 함수 2] 에너지 자립률 → 만족도 보정값 (비선형)

    [이론적 근거]
    에너지 자립률이 시민 만족도에 미치는 영향은 단순 비례가 아니다.
    세종시·부산시 실증 데이터를 기반으로 4개 구간으로 모델링했다:

    구간 설정 근거:
    - 40% 미만: 외부 전력 의존도 60% 이상 → 정전 위험, 에너지 안보 불안
                시민 만족도에 심리적 불안감 반영 (페널티 구간)
    - 40~60%:   불안정하나 위기 수준은 아님 (소폭 페널티 ~ 소폭 보너스)
    - 60~80%:   안정적 공급 달성 → 긍정적 보정 시작
    - 80% 이상: 세종시 로렌하우스 실측값 83.13% 수준 → 완전 자립
                (출처: 세종시 제로에너지건축물 2등급 취득 사례)

    [수정 사항 v2]
    기존 버전에서 페널티 강도(-20점)가 너무 강해
    복지 예산 효과를 완전히 상쇄하는 문제가 있었다.
    → 페널티 최대값을 -12점으로 완화
    → 보너스 최대값은 +20점 유지 (자립 달성의 강력한 인센티브)

    Args:
        rate: 에너지 자립률 (0.0 ~ 1.0)

    Returns:
        만족도 보정값 (-12.0 ~ +20.0)
    """
    if rate < 0.0:
        return -12.0

    elif rate < 0.40:
        # 정전 위험 구간: 선형 패널티
        # 자립률 0% → -12점, 자립률 39% → -0.3점
        # [v2 수정] 기존 -20점 → -12점으로 완화
        # 이유: 예산 배분 효과가 에너지 패널티에 묻히는 문제 해결
        return -12.0 * (1.0 - rate / 0.40)

    elif rate < 0.60:
        # 불안정 구간: -1점 ~ +5점
        progress = (rate - 0.40) / 0.20
        return -1.0 + progress * 6.0

    elif rate < 0.80:
        # 안정 구간: +5점 ~ +13점
        progress = (rate - 0.60) / 0.20
        return 5.0 + progress * 8.0

    else:
        # 자립 달성 구간: +13점 ~ +20점
        # 세종시 목표(83%) 달성 시 +15점 수준
        progress = (rate - 0.80) / 0.20
        return min(20.0, 13.0 + progress * 7.0)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [섹션 3] 에너지원 클래스 계층
# OOP 필수: 상속 + 다형성 (EnergySource → 3개 자식)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class EnergySource:
    """
    [부모 클래스] 에너지원 추상 기반 클래스

    [설계 의도]
    현실의 다양한 에너지원을 OOP로 추상화했다.
    모든 에너지원은 공통적으로:
    - 설치 비율 (capacity_ratio): 전체 에너지 시스템 중 차지하는 비중
    - 상대 비용 (cost_factor):    단위 설치당 비용 (외부전력망 = 1.0 기준)
    - 실효 발전량 (generate):     실제로 자립률에 기여하는 발전량

    [다형성 포인트]
    generate() 메서드는 자식 클래스마다 다르게 구현된다.
    - SolarPanel.generate()  → 날씨 효율(70%) 반영
    - HydrogenCell.generate() → 24시간 안정 효율(90%) 반영
    - ESS.generate()         → 저장 방전 효율(60%) 반영
    - ExternalGrid.generate() → 자립률 기여 없음(0)
    """

    def __init__(self, name: str, capacity_ratio: float, cost_factor: float):
        """
        Args:
            name:           에너지원 이름 (표시용)
            capacity_ratio: 전체 에너지 배분 중 이 에너지원의 비율 (0~1)
            cost_factor:    단위 비용 계수 (ExternalGrid=1.0 기준)
        """
        self.name = name
        self.capacity_ratio = capacity_ratio
        self.cost_factor = cost_factor

    def generate(self) -> float:
        """
        실효 발전량 계산 — 자식 클래스에서 반드시 구현
        반환값이 에너지 자립률 계산에 직접 사용됨
        """
        raise NotImplementedError(
            f"{self.name}: generate() 메서드를 반드시 구현해야 합니다."
        )

    def __str__(self) -> str:
        """사람이 읽기 쉬운 문자열 표현"""
        return f"{self.name}({self.capacity_ratio*100:.0f}%)"

    def __repr__(self) -> str:
        """개발자용 디버깅 표현"""
        return (f"EnergySource(name='{self.name}', "
                f"ratio={self.capacity_ratio:.2f}, "
                f"cost={self.cost_factor})")


class SolarPanel(EnergySource):
    """
    [자식 클래스 1] 태양광 발전

    특성:
    - 설치 비용: 낮음 (cost_factor=0.6)
    - 발전 패턴: 낮에만 발전, 날씨 영향 받음
    - 실효율: 70% (24시간 기준 일조 시간 및 날씨 손실 반영)
    - 단점: 야간·흐린 날 발전 불가 → ESS와 조합 필요

    현실 참조: 세종시 CEMS(커뮤니티 에너지 관리 시스템)의
               태양광 패널 평균 실효율 데이터 기반
    """

    EFFICIENCY = 0.70  # 실효율 상수 (변경 시 이 값만 수정)

    def __init__(self, capacity_ratio: float):
        super().__init__("태양광", capacity_ratio, cost_factor=0.6)

    def generate(self) -> float:
        """
        태양광 실효 발전량
        공식: 설치 비율 × 실효율(0.70)
        """
        return self.capacity_ratio * self.EFFICIENCY


class HydrogenCell(EnergySource):
    """
    [자식 클래스 2] 수소연료전지

    특성:
    - 설치 비용: 높음 (cost_factor=1.4)
    - 발전 패턴: 24시간 안정 발전 (날씨·시간 무관)
    - 실효율: 90% (가장 높은 안정성)
    - 단점: 초기 설치 비용이 비싸 예산 부담 큼

    현실 참조: 세종시 수소 밸류체인 구축 사업의
               수소연료전지 발전 효율 데이터 기반
               (세종시 스마트시티 7대 혁신요소 중 에너지 분야)
    """

    EFFICIENCY = 0.90  # 실효율 상수

    def __init__(self, capacity_ratio: float):
        super().__init__("수소연료전지", capacity_ratio, cost_factor=1.4)

    def generate(self) -> float:
        """
        수소연료전지 실효 발전량
        공식: 설치 비율 × 실효율(0.90)
        """
        return self.capacity_ratio * self.EFFICIENCY


class ESS(EnergySource):
    """
    [자식 클래스 3] 배터리 저장장치 (Energy Storage System)

    특성:
    - 설치 비용: 중간 (cost_factor=0.9)
    - 역할: 태양광 잉여 전력 저장 → 야간/흐린 날 방전
    - 실효율: 60% (충방전 손실 반영)
    - 의의: 태양광의 간헐성 문제를 해결하는 핵심 보완재

    현실 참조: 부산 에코델타 스마트빌리지의
               수열·지열·ESS·태양광 통합 시스템 구성 데이터 기반

    [매직 메서드 활용]
    __len__: 저장 용량 표현 (capacity_ratio × 100을 정수로 반환)
    """

    ROUND_TRIP_EFFICIENCY = 0.60  # 충방전 왕복 효율

    def __init__(self, capacity_ratio: float):
        super().__init__("ESS", capacity_ratio, cost_factor=0.9)
        self.stored_energy: float = 0.0  # 현재 저장된 에너지량

    def generate(self) -> float:
        """
        ESS 실효 발전량 (방전 기준)
        공식: 설치 비율 × 왕복 효율(0.60)
        """
        return self.capacity_ratio * self.ROUND_TRIP_EFFICIENCY

    def charge(self, surplus: float) -> None:
        """
        잉여 전력 저장
        Args:
            surplus: 저장할 잉여 전력량
        """
        self.stored_energy += surplus

    def discharge(self) -> float:
        """
        저장 전력 방전 및 초기화
        Returns:
            방전된 전력량
        """
        released = self.stored_energy
        self.stored_energy = 0.0
        return released

    def __len__(self) -> int:
        """
        [매직 메서드 __len__]
        ESS 용량을 정수로 반환 (0~100)
        용도: len(ess_instance)로 용량 확인 가능
        """
        return int(self.capacity_ratio * 100)


class ExternalGrid(EnergySource):
    """
    [자식 클래스 4] 외부 전력망

    특성:
    - 비용: 기준값 (cost_factor=1.0)
    - 안정성: 높음 (24시간 공급)
    - 자립률 기여: 0% (외부 의존이므로 자립률에 포함 안 됨)
    - 의미: 외부전력망 비율이 높을수록 에너지 자립 실패

    정책적 의의:
    에너지 안보 관점에서 외부 전력 의존은
    외부 충격(전쟁, 재난, 가격 급등)에 취약한 구조다.
    이 시뮬레이터에서 ExternalGrid 비율을 줄이는 것이
    에너지 자립형 스마트시티의 핵심 목표다.
    """

    def __init__(self, capacity_ratio: float):
        super().__init__("외부전력망", capacity_ratio, cost_factor=1.0)

    def generate(self) -> float:
        """
        외부전력망은 에너지 자립률에 기여하지 않음
        → 항상 0.0 반환
        """
        return 0.0  # 자립률 기여 없음 — 의도된 설계


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [섹션 4] 시민 클래스 계층
# OOP 필수: 상속 + 다형성 (Citizen → 5개 자식)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Citizen:
    """
    [부모 클래스] 시민 추상 기반 클래스

    [설계 근거: IMD Smart City Index 5개 니즈 벡터]
    IMD는 시민 만족도를 5개 영역으로 측정한다:
      1. health_safety  (건강·안전): 의료, 치안, 재난 대응
      2. mobility       (모빌리티):  교통, 이동, 대중교통
      3. activities     (활동·문화): 여가, 문화, 스포츠
      4. opportunities  (기회·교육): 일자리, 교육, 디지털 접근
      5. governance     (거버넌스):  시민 참여, 정책 투명성

    출처: IMD Smart City Index 2024, Methodology Section
    (각 도시 시민 120명 대상 설문, 5개 영역 평가)

    [다형성 포인트]
    satisfaction_weight()는 자식 클래스마다 다른 가중치를 반환한다.
    모든 자식 클래스의 가중치 합계는 반드시 1.0이어야 한다.

    [v2 설계 개선]
    기존 3분류(Worker/Student/Elder)의 문제:
    ① 비근로자(전업주부, 실업자) 누락
    ② Worker·Student는 역할 기준, Elder는 연령 기준으로 축 불일치
    → 5분류로 확장, IMD 니즈 기반으로 분류 기준 통일
    """

    def __init__(self, name: str):
        self.name = name

    def satisfaction_weight(self) -> Dict[str, float]:
        """
        5개 니즈 영역별 가중치 반환
        자식 클래스에서 반드시 구현해야 함
        합계: 1.0 보장 필수
        """
        raise NotImplementedError(
            f"{self.name}: satisfaction_weight()를 반드시 구현해야 합니다."
        )

    def __str__(self) -> str:
        """
        [매직 메서드 __str__]
        사람이 읽기 쉬운 표현: 시민 유형과 핵심 니즈 표시
        """
        weights = self.satisfaction_weight()
        top_need = max(weights, key=weights.get)
        need_names = {
            "health_safety": "건강·안전",
            "mobility": "모빌리티",
            "activities": "활동·문화",
            "opportunities": "기회·교육",
            "governance": "거버넌스"
        }
        return f"{self.name}(핵심니즈: {need_names.get(top_need, top_need)})"

    def __repr__(self) -> str:
        """
        [매직 메서드 __repr__]
        개발자용 디버깅 표현
        """
        return f"Citizen(type='{self.name}')"


class Worker(Citizen):
    """
    [자식 클래스 1] 경제활동 근로자

    [가중치 설계 근거]
    - 모빌리티(0.38): 매일 출퇴근하는 근로자에게 교통은 삶의 질 직결 요인
                      서울 IMD 2024 시민 불만 1위: 도로 교통체증
    - 기회·교육(0.27): 커리어 성장, 재교육, 고용 안정성에 민감
    - 건강·안전(0.15): 산업 안전, 의료 접근성 중시
    - 활동·문화(0.12): 여가 시간 문화 활동 (낮은 우선순위)
    - 거버넌스(0.08):  노동 정책보다 개인 이동성에 더 민감

    출처 근거: IMD SCI 2024 서울 분석 — 모빌리티 분야가
              기술 점수 대비 상대적 약점으로 지적됨
    """

    def __init__(self):
        super().__init__("근로자")

    def satisfaction_weight(self) -> Dict[str, float]:
        return {
            "health_safety":  0.15,
            "mobility":       0.38,   # ★ 핵심 니즈: 교통·이동
            "activities":     0.12,
            "opportunities":  0.27,   # ★ 2순위: 일자리·교육
            "governance":     0.08
        }  # 합계: 1.00


class Student(Citizen):
    """
    [자식 클래스 2] 학령기·대학생

    [가중치 설계 근거]
    - 기회·교육(0.37): 취업·학점이 대학생의 제1 관심사
                       디지털 인프라, 교육 환경 민감
    - 활동·문화(0.28): 대학가 특성상 문화·여가 인프라 민감도 높음
                       B구역(대학가)의 핵심 특성
    - 모빌리티(0.18):  등하교 교통 (근로자보다 낮음 — 자전거, 도보 대안 있음)
    - 건강·안전(0.10): 상대적으로 건강 위험 낮은 연령대
    - 거버넌스(0.07):  정책 참여 관심 낮음 (청년 정치 무관심 반영)

    [설계 고려사항]
    Student의 activities 가중치(0.28)가 비교적 높은 이유:
    대학가(B구역)는 문화·여가 인프라가 만족도에 큰 영향을 미치며,
    이는 B구역이 교육 예산과 함께 활동 예산에도 민감하다는 것을 의미한다.
    """

    def __init__(self):
        super().__init__("학생")

    def satisfaction_weight(self) -> Dict[str, float]:
        return {
            "health_safety":  0.10,
            "mobility":       0.18,
            "activities":     0.28,   # ★ 2순위: 문화·여가 (대학가 특성)
            "opportunities":  0.37,   # ★ 핵심 니즈: 취업·교육
            "governance":     0.07
        }  # 합계: 1.00


class Caregiver(Citizen):
    """
    [자식 클래스 3] 전업주부·육아·돌봄 담당자

    [가중치 설계 근거]
    - 건강·안전(0.38): 아이·가족의 건강과 안전이 최우선
                       보육 시설 안전, 의료 접근성, 치안
    - 거버넌스(0.22):  복지 정책의 직접 수혜자
                       보육비 지원, 육아 정책에 가장 민감한 집단
                       정책 결정 과정에서 소외되기 쉬운 집단 특성 반영
    - 모빌리티(0.20):  아이 등하교, 병원 방문, 장보기 이동
    - 활동·문화(0.12): 육아 문화 프로그램, 공원, 도서관
    - 기회·교육(0.08): 재취업 의향 있으나 현재 우선순위 낮음

    [사회과학적 의의]
    Caregiver는 기존 3분류에서 완전히 누락된 집단이다.
    한국의 성별 돌봄 노동 현실(여성 중심 육아)을 반영하며,
    이 집단의 거버넌스 민감도가 높다는 것은 정책 참여 소외를 의미한다.
    (참조: Shin et al., 2025 — 한국 스마트시티의 공급자 중심 문제)
    """

    def __init__(self):
        super().__init__("돌봄담당자")

    def satisfaction_weight(self) -> Dict[str, float]:
        return {
            "health_safety":  0.38,   # ★ 핵심 니즈: 가족 안전
            "mobility":       0.20,
            "activities":     0.12,
            "opportunities":  0.08,
            "governance":     0.22    # ★ 2순위: 복지 정책 참여
        }  # 합계: 1.00


class Unemployed(Citizen):
    """
    [자식 클래스 4] 실업·구직자

    [가중치 설계 근거]
    - 기회·교육(0.42): 일자리가 유일하고 절대적인 관심사
                       직업훈련, 취업 지원 서비스, 고용 인프라
    - 거버넌스(0.25):  정부 지원 프로그램의 직접 수혜자
                       실업급여, 취업 지원 정책 투명성에 가장 예민
                       "정부가 나를 돕고 있는가"에 대한 체감 의존도 최고
    - 건강·안전(0.18): 경제적 취약으로 의료비 부담 가중
    - 모빌리티(0.10):  구직 활동을 위한 이동 (낮은 우선순위)
    - 활동·문화(0.05): 여가 지출 여력 없음

    [사회과학적 의의]
    기회와 거버넌스 가중치 합계(0.67)가 가장 높은 집단이다.
    이는 Unemployed가 정부 정책의 방향성에 가장 민감하게 반응함을 의미하며,
    거버넌스 예산 삭감 시 이 집단이 가장 큰 타격을 받는다.
    """

    def __init__(self):
        super().__init__("실업자")

    def satisfaction_weight(self) -> Dict[str, float]:
        return {
            "health_safety":  0.18,
            "mobility":       0.10,
            "activities":     0.05,
            "opportunities":  0.42,   # ★ 핵심 니즈: 일자리
            "governance":     0.25    # ★ 2순위: 정책 지원 체감
        }  # 합계: 1.00


class Elder(Citizen):
    """
    [자식 클래스 5] 은퇴 이후 노인

    [가중치 설계 근거]
    - 건강·안전(0.42): 의료 접근성이 생존과 직결
                       만성질환 관리, 응급 의료, 요양 서비스
    - 모빌리티(0.25):  병원 이동 수단이 없으면 건강·안전도 의미없음
                       (버스 → 병원 경로가 삶의 핵심 동선)
    - 거버넌스(0.18):  연금·요양 정책 수혜자
                       복지 정책 결정에 대한 참여 욕구 높음
    - 활동·문화(0.10): 노인 여가 프로그램, 경로당, 공원
    - 기회·교육(0.05): 은퇴 후 재취업 의향 낮음

    [v2 수정]
    기존 모빌리티 가중치(0.23) → (0.25)로 상향
    근거: 고령화 사회에서 노인 이동권이 독립 생활의 핵심 조건이며,
          병원 접근성과 건강·안전은 분리할 수 없는 연결 고리
    """

    def __init__(self):
        super().__init__("노인")

    def satisfaction_weight(self) -> Dict[str, float]:
        return {
            "health_safety":  0.42,   # ★ 핵심 니즈: 의료·안전
            "mobility":       0.25,   # ★ 2순위: 병원 이동 (v2 상향)
            "activities":     0.10,
            "opportunities":  0.05,
            "governance":     0.18
        }  # 합계: 1.00


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [섹션 5] 예산 자원 클래스
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Resource:
    """
    예산 배분 관리 클래스

    [5개 예산 항목]
    기존 4개(복지/교육/인프라/안전)에서 에너지인프라를 분리하여 5개로 확장.
    이 분리가 에너지-예산 선순환 구조의 출발점이다:
      에너지인프라 투자 → 자립률 상승 → 운영비 절감 → 예산 환원

    [예산 → 니즈 매핑: 1:다 가중 매핑 방식]
    예산 항목 하나가 여러 니즈 영역에 영향을 주는 구조.
    (1:1 매핑의 경우 '활동·문화' 니즈가 커버되지 않는 문제 해결)

    매핑 비율 설계 근거:
    - 복지(welfare):
        건강·안전(0.65): 의료비 지원, 돌봄 서비스 → 직접 연결
        활동·문화(0.20): 복지관, 노인센터 → 간접 연결
        거버넌스(0.15):  복지 정책 참여 채널 운영 → 간접 연결

    - 교육(education):
        기회·교육(0.65): 학교, 직업훈련 → 직접 연결
        활동·문화(0.25): 도서관, 문화센터, 평생학습원 → 간접 연결
        거버넌스(0.10):  교육 정책 공론화 → 간접 연결

    - 에너지인프라(energy_infra):
        거버넌스(0.45):  에너지 정책 참여, 스마트그리드 시민 참여
        모빌리티(0.35):  전기차 충전 인프라, 친환경 교통
        건강·안전(0.20): 안정적 전력 → 의료장비, 응급 시스템

    - 일반인프라(general_infra):
        모빌리티(0.75):  도로, 교통, 대중교통 → 직접 연결
        건강·안전(0.15): 보행로 안전, 가로등
        활동·문화(0.10): 공원, 광장 조성

    - 안전(safety):
        건강·안전(0.60): 치안, 소방, 재난 대응 → 직접 연결
        거버넌스(0.25):  치안 정책 투명성, CCTV 윤리 거버넌스
        모빌리티(0.15):  교통 안전, 보행자 보호

    [매직 메서드 활용]
    __add__: 두 Resource 합산 → 에너지 절감액 재배분에 활용
    __str__: 예산 현황 한눈에 표시
    __repr__: 개발자용 디버깅
    """

    # 예산 → 니즈 매핑 테이블 (클래스 변수 — 모든 인스턴스 공유)
    BUDGET_TO_NEED: Dict[str, Dict[str, float]] = {
        "welfare": {
            "health_safety":  0.65,
            "activities":     0.20,
            "governance":     0.15
        },
        "education": {
            "opportunities":  0.65,
            "activities":     0.25,
            "governance":     0.10
        },
        "energy_infra": {
            "governance":     0.45,
            "mobility":       0.35,
            "health_safety":  0.20
        },
        "general_infra": {
            "mobility":       0.75,
            "health_safety":  0.15,
            "activities":     0.10
        },
        "safety": {
            "health_safety":  0.60,
            "governance":     0.25,
            "mobility":       0.15
        }
    }

    def __init__(self,
                 welfare: float,
                 education: float,
                 energy_infra: float,
                 general_infra: float,
                 safety: float):
        """
        Args:
            welfare:       복지 예산 비율 (0~1)
            education:     교육 예산 비율 (0~1)
            energy_infra:  에너지 인프라 예산 비율 (0~1)
            general_infra: 일반 인프라 예산 비율 (0~1)
            safety:        안전 예산 비율 (0~1)

        Raises:
            BudgetAllocationError: 합계가 100%가 아닐 때
        """
        total = welfare + education + energy_infra + general_infra + safety
        if abs(total - 1.0) > 0.005:
            raise BudgetAllocationError(round(total * 100, 1))

        self.welfare = welfare
        self.education = education
        self.energy_infra = energy_infra
        self.general_infra = general_infra
        self.safety = safety

    def as_dict(self) -> Dict[str, float]:
        """예산 딕셔너리 반환 (내부 연산용)"""
        return {
            "welfare":       self.welfare,
            "education":     self.education,
            "energy_infra":  self.energy_infra,
            "general_infra": self.general_infra,
            "safety":        self.safety
        }

    def get_need_ratios(self) -> Dict[str, float]:
        """
        예산 배분 → 5개 니즈 도달 비율 계산
        BUDGET_TO_NEED 매핑 테이블을 사용하여
        각 니즈 영역에 최종적으로 도달하는 예산 비율을 산출한다.

        예시:
            복지 30% → 건강·안전에 30%×0.65=19.5% 도달
            안전 10% → 건강·안전에 10%×0.60=6% 도달
            → 건강·안전 총 도달 비율: 19.5%+6%+... = 합산
        """
        needs: Dict[str, float] = {
            "health_safety":  0.0,
            "mobility":       0.0,
            "activities":     0.0,
            "opportunities":  0.0,
            "governance":     0.0
        }
        budget = self.as_dict()

        for budget_key, budget_ratio in budget.items():
            mapping = self.BUDGET_TO_NEED[budget_key]
            for need_key, map_ratio in mapping.items():
                needs[need_key] += budget_ratio * map_ratio

        return needs

    def __add__(self, other: 'Resource') -> 'Resource':
        """
        [매직 메서드 __add__]
        두 Resource 합산 후 정규화

        용도: 에너지 절감액을 기존 예산에 추가할 때 사용
        예시: adjusted_resource = original_resource + savings_resource

        정규화 처리: 합산 후 총합이 1.0이 되도록 각 항목 비율 조정
        """
        raw = Resource.__new__(Resource)
        raw.welfare       = self.welfare       + other.welfare
        raw.education     = self.education     + other.education
        raw.energy_infra  = self.energy_infra  + other.energy_infra
        raw.general_infra = self.general_infra + other.general_infra
        raw.safety        = self.safety        + other.safety

        total = (raw.welfare + raw.education + raw.energy_infra
                 + raw.general_infra + raw.safety)

        # 정규화: 합계가 1.0이 되도록 조정
        factor = 1.0 / total if total > 0 else 1.0
        raw.welfare       *= factor
        raw.education     *= factor
        raw.energy_infra  *= factor
        raw.general_infra *= factor
        raw.safety        *= factor

        return raw

    def __str__(self) -> str:
        """
        [매직 메서드 __str__]
        예산 현황 한눈에 표시
        """
        return (f"복지{self.welfare*100:.1f}% | "
                f"교육{self.education*100:.1f}% | "
                f"에너지{self.energy_infra*100:.1f}% | "
                f"인프라{self.general_infra*100:.1f}% | "
                f"안전{self.safety*100:.1f}%")

    def __repr__(self) -> str:
        """[매직 메서드 __repr__] 개발자용"""
        return f"Resource({self.as_dict()})"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [섹션 6] 에너지 그리드
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class EnergyGrid:
    """
    도시 전체 에너지 시스템 관리

    [에너지-예산 선순환 구조의 핵심]
    이 클래스가 에너지와 예산을 연결하는 중간 다리 역할을 한다:

    에너지인프라 예산 투입
         ↓
    에너지원 구성 결정 (EnergyGrid)
         ↓
    에너지 자립률 계산 (calculate_independence_rate)
         ↓
    외부 전력 구매비 절감 (calculate_savings)
         ↓
    절감액이 복지·교육 예산으로 환원
         ↓
    시민 만족도 추가 상승

    [자립률 계산 원리]
    총 설치 용량 대비 자체 발전량(외부전력망 제외)의 비율
    ExternalGrid는 generate()가 0을 반환하므로 자립률에 포함 안 됨

    [__len__ 매직 메서드]
    에너지원 개수 반환: len(energy_grid) → 4 (4개 에너지원)
    """

    # 에너지 운영 기본 비용 (전체 예산 대비 외부 전력 구매 비율)
    BASE_EXTERNAL_COST = 0.08  # 자립률 0%일 때 전체 예산의 8%가 전기료

    def __init__(self, sources: List[EnergySource]):
        """
        Args:
            sources: 에너지원 리스트 (비율 합계 = 1.0 필수)

        Raises:
            EnergyAllocationError: 에너지원 비율 합계가 100%가 아닐 때
        """
        total = sum(s.capacity_ratio for s in sources)
        if abs(total - 1.0) > 0.005:
            raise EnergyAllocationError(round(total * 100, 1))
        self.sources = sources

    def calculate_independence_rate(self) -> float:
        """
        에너지 자립률 계산

        공식:
            자립률 = 총 자체 발전량 / 총 설치 용량
                   = Σ(source.generate()) / Σ(source.capacity_ratio)

        ExternalGrid는 generate() = 0이므로 자립률 분자에 포함되지 않음
        최대 1.0(100%)으로 클램핑

        Returns:
            에너지 자립률 (0.0 ~ 1.0)
        """
        total_self_generation = sum(s.generate() for s in self.sources)
        total_capacity = sum(s.capacity_ratio for s in self.sources)

        if total_capacity == 0:
            return 0.0
        return min(1.0, total_self_generation / total_capacity)

    def calculate_savings(self, independence_rate: float) -> float:
        """
        에너지 자립에 의한 예산 절감액 계산

        [선순환 메커니즘]
        자립률이 높을수록 외부 전력 구매비가 줄어들고,
        절감된 비용이 다른 예산 항목으로 환원된다.

        공식:
            절감액 = 기본 외부 전력 비용 × 자립률
                   = 0.08 × independence_rate

        예시:
            자립률 0%  → 절감액 0%    (전액 외부 구매)
            자립률 50% → 절감액 4%    (절반 절감)
            자립률 80% → 절감액 6.4%  (세종시 목표 수준)

        Args:
            independence_rate: 에너지 자립률 (0.0 ~ 1.0)

        Returns:
            절감된 예산 비율 (0.0 ~ 0.08)
        """
        return self.BASE_EXTERNAL_COST * independence_rate

    def __len__(self) -> int:
        """
        [매직 메서드 __len__]
        에너지원 종류 개수 반환
        """
        return len(self.sources)

    def __str__(self) -> str:
        """[매직 메서드 __str__] 에너지 구성 현황 표시"""
        rate = self.calculate_independence_rate()
        sources_str = " | ".join(str(s) for s in self.sources)
        return f"EnergyGrid[{sources_str}] → 자립률 {rate*100:.1f}%"

    def __repr__(self) -> str:
        """[매직 메서드 __repr__] 개발자용"""
        return f"EnergyGrid(sources={[s.name for s in self.sources]})"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [섹션 7] 구역 클래스
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class District:
    """
    도시 구역 — 시민 만족도 계산의 기본 단위

    [구역 설계 원칙]
    5개 구역은 현실의 도시 구조를 반영한다:
    - A구역(산업단지): Worker 집중 → 모빌리티·기회 민감
    - B구역(대학가):   Student 집중 → 교육·문화 민감
    - C구역(복지타운): Elder 집중   → 건강·안전 민감
    - D구역(신도시):   혼합 구성    → 균형 잡힌 수요
    - E구역(구도심):   혼합 구성    → 거버넌스·안전 취약

    [v2 수정: 시민 구성 비율 조정]
    A구역 Worker: 70% → 75% (변화 가시성 향상)
    C구역 Elder:  65% → 75% (복지 예산 민감도 향상)
    목적: 현실 범위 내에서 트레이드오프가 명확히 드러나도록 설계

    [만족도 계산 4단계]
    1. 예산 → 니즈 도달 비율 계산 (Resource.get_need_ratios)
    2. 비선형 변환 (budget_to_fulfillment)
    3. 시민 유형별 가중치 × 니즈 점수 가중 평균
    4. 에너지 자립률 보정 적용

    [__len__ 매직 메서드]
    시민 유형 수 반환: len(district) → 5 (5종류 시민)
    """

    SATISFACTION_THRESHOLD = 50.0  # 위험 구역 임계치 (0~100점 기준)

    def __init__(self,
                 name: str,
                 citizen_composition: Dict[Citizen, float],
                 initial_energy_rate: float = 0.42):
        """
        Args:
            name:                구역 이름 (표시용)
            citizen_composition: 시민 유형 → 구성 비율 딕셔너리 (합계 = 1.0)
            initial_energy_rate: 초기 에너지 자립률 (v2: 기본값 0.42로 상향)

        Raises:
            ValueError: 시민 구성 비율 합계가 1.0이 아닐 때
        """
        total = sum(citizen_composition.values())
        if abs(total - 1.0) > 0.005:
            raise ValueError(
                f"{name} 구역 시민 구성 비율 합계 오류: {total:.3f} (1.0이어야 함)"
            )

        self.name = name
        self.citizen_composition = citizen_composition
        self.energy_rate = initial_energy_rate
        self._last_score: float = 0.0  # 마지막 계산된 만족도 (내부 저장)

    def calculate_satisfaction(self, resource: Resource) -> float:
        """
        구역 시민 만족도 계산 (4단계 파이프라인)

        [1단계] 예산 → 니즈 도달 비율
            Resource.get_need_ratios()를 통해
            예산 배분이 5개 니즈 영역에 어떻게 도달하는지 계산

        [2단계] 비선형 충족도 변환
            budget_to_fulfillment()로 비율을 0~100 점수로 변환
            임계점(20%) 전후로 급격한 변화 발생

        [3단계] 시민 가중 평균
            각 시민 유형의 satisfaction_weight()와 니즈 점수를 곱하고
            구역 내 시민 구성 비율로 가중 평균

        [4단계] 에너지 보정
            에너지 자립률에 따른 보정값을 최종 점수에 가산

        Args:
            resource: 현재 예산 배분 (절감액 재배분 후 조정된 값)

        Returns:
            구역 만족도 (0.0 ~ 100.0)

        Raises:
            LowSatisfactionWarning: 만족도가 임계치(50점) 이하일 때
        """
        # ── 1단계: 예산 → 니즈 도달 비율 ──
        need_ratios = resource.get_need_ratios()

        # ── 2단계: 비선형 변환 (핵심 함수 적용) ──
        need_scores: Dict[str, float] = {}
        for need, ratio in need_ratios.items():
            need_scores[need] = budget_to_fulfillment(ratio, threshold=0.20)

        # ── 3단계: 시민 유형별 가중 평균 ──
        district_raw_score = 0.0
        for citizen, comp_ratio in self.citizen_composition.items():
            weights = citizen.satisfaction_weight()
            # 각 시민의 만족도 = Σ(니즈 가중치 × 니즈 점수)
            citizen_score = sum(
                weights[need] * need_scores[need]
                for need in weights
            )
            district_raw_score += comp_ratio * citizen_score

        # ── 4단계: 에너지 자립률 보정 ──
        energy_bonus = energy_to_bonus(self.energy_rate)
        final_score = max(0.0, min(100.0, district_raw_score + energy_bonus))

        self._last_score = final_score  # 내부 저장

        # 위험 구역 경보 발생
        if final_score < self.SATISFACTION_THRESHOLD:
            raise LowSatisfactionWarning(self.name, final_score)

        return final_score

    def __len__(self) -> int:
        """
        [매직 메서드 __len__]
        이 구역의 시민 유형 수 반환
        """
        return len(self.citizen_composition)

    def __str__(self) -> str:
        """[매직 메서드 __str__] 구역 현황 표시"""
        score_str = (f"{self._last_score:.1f}점"
                     if self._last_score > 0 else "미계산")
        return (f"[{self.name}] 만족도: {score_str} | "
                f"에너지 자립률: {self.energy_rate*100:.0f}% | "
                f"시민 유형: {len(self)}종")

    def __repr__(self) -> str:
        """[매직 메서드 __repr__] 개발자용"""
        return f"District(name='{self.name}', citizens={len(self)})"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [섹션 8] 도시 클래스
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class City:
    """
    NOVA시 — 5개 구역 통합 관리

    [apply_policy: 에너지-예산 선순환의 완전한 구현]

    정책 적용 시 다음 순서로 처리된다:
    1. 에너지 자립률 계산
    2. 절감액 산출 (에너지 비용 절약분)
    3. 절감액을 복지·교육에 재배분 (선순환 핵심)
    4. 조정된 예산으로 각 구역 만족도 계산

    이 구조가 "에너지가 예산과 따로 논다"는 문제를 해결한다:
    에너지에 투자할수록 → 자립률 상승 → 운영비 절감 → 예산 여유 → 복지 향상
    즉, 에너지 투자가 장기적으로 시민 만족도를 두 경로로 동시에 높인다.
    """

    def __init__(self, name: str, districts: List[District]):
        self.name = name
        self.districts = districts

    def apply_policy(self,
                     resource: Resource,
                     energy_grid: EnergyGrid) -> Dict:
        """
        정책 적용 및 전체 결과 계산

        [선순환 메커니즘 상세]
        절감액 재배분 비율:
        - 복지 50%: Elder·Caregiver 만족도 향상
        - 교육 50%: Student·Worker 만족도 향상

        이 비율은 팀 합의로 조정 가능하며,
        "누구를 위한 선순환인가"라는 정책 결정의 축소판이다.

        Args:
            resource:     현재 예산 배분 설정
            energy_grid:  현재 에너지원 구성

        Returns:
            결과 딕셔너리:
            - independence_rate: 에너지 자립률
            - savings:           절감된 예산 비율
            - adjusted_budget:   절감액 반영 후 조정 예산
            - districts:         구역별 만족도 딕셔너리
            - city_average:      도시 전체 평균 만족도
            - warnings:          위험 구역 경보 리스트
        """
        # ── 에너지 자립률 및 절감액 계산 ──
        independence_rate = energy_grid.calculate_independence_rate()
        savings = energy_grid.calculate_savings(independence_rate)

        # ── 구역별 에너지 자립률 업데이트 ──
        for district in self.districts:
            district.energy_rate = independence_rate

        # ── 절감액 재배분 (선순환 핵심) ──
        # 절감액의 50%는 복지, 50%는 교육으로 환원
        savings_resource = Resource.__new__(Resource)
        savings_resource.welfare       = savings * 0.50
        savings_resource.education     = savings * 0.50
        savings_resource.energy_infra  = 0.0
        savings_resource.general_infra = 0.0
        savings_resource.safety        = 0.0

        # 기존 예산에 절감액 추가 후 정규화 (__add__ 활용)
        adjusted = resource + savings_resource

        # ── 구역별 만족도 계산 ──
        results = {
            "independence_rate": independence_rate,
            "savings":           savings,
            "adjusted_budget":   adjusted,
            "districts":         {},
            "warnings":          []
        }

        for district in self.districts:
            try:
                score = district.calculate_satisfaction(adjusted)
                results["districts"][district.name] = score
            except LowSatisfactionWarning as e:
                # 위험 구역: 점수 저장 + 경보 기록
                results["districts"][district.name] = district._last_score
                results["warnings"].append(str(e))

        # 도시 전체 평균
        results["city_average"] = (
            sum(results["districts"].values()) / len(self.districts)
        )

        return results

    def __str__(self) -> str:
        return f"City('{self.name}', 구역 수: {len(self.districts)})"

    def __repr__(self) -> str:
        return f"City(name='{self.name}', districts={[d.name for d in self.districts]})"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [섹션 9] 정책 시뮬레이터
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PolicySimulator:
    """
    시뮬레이션 실행 및 시나리오 비교 분석

    [역할]
    City.apply_policy()를 반복 호출하며 결과를 축적하고,
    시나리오 간 비교 분석을 제공한다.

    [히스토리 관리]
    모든 실행 결과를 self.history에 저장하여
    시간 순서에 따른 정책 변화 추적이 가능하다.
    """

    def __init__(self, city: City):
        self.city = city
        self.history: List[Dict] = []  # 전체 실행 이력

    def run(self,
            resource: Resource,
            energy_grid: EnergyGrid,
            scenario_name: str = "사용자 입력") -> Dict:
        """
        단일 시나리오 실행

        Args:
            resource:       예산 배분 설정
            energy_grid:    에너지원 구성
            scenario_name:  시나리오 이름 (표시용)

        Returns:
            실행 결과 딕셔너리 (City.apply_policy 결과 + 메타 정보)
        """
        result = self.city.apply_policy(resource, energy_grid)
        result["scenario"]     = scenario_name
        result["resource"]     = resource
        result["energy_grid"]  = energy_grid
        self.history.append(result)
        return result

    def compare(self, result_a: Dict, result_b: Dict) -> Dict:
        """
        두 시나리오 비교 분석

        Args:
            result_a: 비교 기준 시나리오 결과
            result_b: 비교 대상 시나리오 결과

        Returns:
            비교 결과 딕셔너리:
            - city_avg_change:    도시 평균 만족도 변화량
            - independence_change: 에너지 자립률 변화량 (%p)
            - district_changes:   구역별 만족도 변화량
        """
        return {
            "scenario_a":          result_a["scenario"],
            "scenario_b":          result_b["scenario"],
            "city_avg_change":     (result_b["city_average"]
                                    - result_a["city_average"]),
            "independence_change": ((result_b["independence_rate"]
                                     - result_a["independence_rate"]) * 100),
            "savings_change":      ((result_b["savings"]
                                     - result_a["savings"]) * 100),
            "district_changes":    {
                d_name: result_b["districts"][d_name] - result_a["districts"][d_name]
                for d_name in result_a["districts"]
            }
        }

    def __str__(self) -> str:
        return (f"PolicySimulator("
                f"도시: {self.city.name}, "
                f"실행 횟수: {len(self.history)}회)")

    def __repr__(self) -> str:
        return f"PolicySimulator(city='{self.city.name}')"
