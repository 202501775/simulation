"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
simulation_v3.py  (커스텀 시나리오 전용 수정본)
NOVA시 스마트시티 자원 배분 시뮬레이터 v3.0

[수정 사항]
- 기존 고정 시나리오를 모두 제거하고, 사용자 입력(커스텀) 시나리오만 실행하도록 변경
- 기존 시나리오 삭제로 인해 발생하던 하단 비교 분석/평가 코드의 KeyError 오류 완전 해결
- 사용자 입력값에 대한 정상 출력 및 요약 테이블 기능 유지
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import sys
from typing import Dict, List

# Windows 환경 및 로컬 실행을 위해 기존 리눅스 전용 경로는 주석 처리합니다.
# `classes.py` 파일이 이 파일과 같은 폴더에 있으면 정상 작동합니다.
# sys.path.insert(0, '/home/claude/nova_v2')

from classes import (
    Worker, Student, Caregiver, Unemployed, Elder,
    SolarPanel, HydrogenCell, ESS, ExternalGrid,
    Resource, EnergyGrid, District, City, PolicySimulator,
    budget_to_fulfillment, energy_to_bonus,
    BudgetAllocationError, LowSatisfactionWarning, EnergyAllocationError
)


def verify_core_functions():
    print("=" * 65)
    print("  【 핵심 함수 검증 】")
    print("=" * 65)

    print("\n  ▶ [함수 1] 예산 비율 → 니즈 충족도 (비선형 변환)")
    print("    이론 근거: 공공재 임계점 이론 + 한계효용 체감 법칙")
    print(f"\n    {'예산비율':>8} │ {'충족도':>7} │ {'구간':>10} │ {'설명'}")
    print("    " + "─" * 62)

    cases = [
        (0.00, "급락구간", "예산 0 — 서비스 완전 붕괴"),
        (0.05, "급락구간", "임계점 1/4 — 기본 수요 미충족"),
        (0.10, "급락→부족", "임계점 1/2 — 급락 구간 끝 (40점)"),
        (0.15, "부족구간", "임계점 3/4 — 부족 구간 (50점)"),
        (0.20, "★임계점", "★ 임계점 도달 — 기준선 (60점)"),
        (0.25, "적정구간", "적정 구간 진입 (67.5점)"),
        (0.30, "적정구간", "적정 구간 중반 (75점)"),
        (0.40, "체감구간", "적정 구간 상단 — 한계효용 체감 시작"),
        (0.50, "체감구간", "과잉 투자 구간"),
    ]
    for r, zone, desc in cases:
        s = budget_to_fulfillment(r, 0.20)
        print(f"    {r*100:>7.0f}% │ {s:>6.1f}점 │ {zone:>10} │ {desc}")

    print("\n    ★ 핵심: 예산 10%→20% 구간에서 40점→60점 (+20점 점프)")
    print("       이 임계점 돌파가 발표 시연의 클라이맥스")

    print("\n\n  ▶ [함수 2] 에너지 자립률 → 만족도 보정 (v2: 페널티 완화)")
    print("    현실 근거: 세종시 83.13% 목표, 부산 스마트빌리지 60% 수준")
    print(f"\n    {'자립률':>7} │ {'보정값':>8} │ {'상태':>10} │ {'설명'}")
    print("    " + "─" * 60)

    e_cases = [
        (0.00, "정전위험", "⚠️ 완전 외부 의존 — 최대 패널티"),
        (0.20, "정전위험", "⚠️ 위험 구간"),
        (0.39, "정전위험", "⚠️ 임계점 직전"),
        (0.42, "불안정", "불안정 구간 진입"),
        (0.60, "안정", "✅ 안정 구간 진입"),
        (0.70, "안정", "안정 구간 중반"),
        (0.80, "자립달성", "✅ 자립 달성"),
        (0.83, "자립달성", "★ 세종시 로렌하우스 실측값 (83.13%)"),
        (1.00, "자립달성", "완전 자립"),
    ]
    for rate, state, desc in e_cases:
        bonus = energy_to_bonus(rate)
        print(f"    {rate*100:>6.0f}% │ {bonus:>+7.1f}점 │ {state:>10} │ {desc}")
    print("\n    v2 수정: 최대 페널티 -20점 → -12점 완화")
    print("    이유: 에너지 패널티가 예산 배분 효과를 완전 상쇄하는 문제 해결")


def build_nova_city() -> City:
    worker     = Worker()
    student    = Student()
    caregiver  = Caregiver()
    unemployed = Unemployed()
    elder      = Elder()

    districts = [
        District(
            name="A구역(산업단지)",
            citizen_composition={
                worker: 0.75, student: 0.05, caregiver: 0.08,
                unemployed: 0.07, elder: 0.05
            },
            initial_energy_rate=0.45
        ),
        District(
            name="B구역(대학가)",
            citizen_composition={
                worker: 0.10, student: 0.70, caregiver: 0.08,
                unemployed: 0.07, elder: 0.05
            },
            initial_energy_rate=0.42
        ),
        District(
            name="C구역(복지타운)",
            citizen_composition={
                worker: 0.05, student: 0.03, caregiver: 0.10,
                unemployed: 0.07, elder: 0.75
            },
            initial_energy_rate=0.55
        ),
        District(
            name="D구역(신도시)",
            citizen_composition={
                worker: 0.35, student: 0.25, caregiver: 0.20,
                unemployed: 0.10, elder: 0.10
            },
            initial_energy_rate=0.40
        ),
        District(
            name="E구역(구도심)",
            citizen_composition={
                worker: 0.30, student: 0.05, caregiver: 0.20,
                unemployed: 0.18, elder: 0.27
            },
            initial_energy_rate=0.30
        )
    ]
    return City("NOVA시", districts)


def define_scenarios() -> Dict:
    """
    기존 고정 시나리오를 비워두고 빈 딕셔너리를 반환합니다.
    """
    scenarios = {}
    return scenarios


def get_user_scenario():
    print("\n\n" + "=" * 65)
    print("  【 🛠️ 사용자 정의 시나리오 가중치 입력 】")
    print("  소수점 단위로 입력해 주세요. 합계는 반드시 1.0(100%)이어야 합니다.")
    print("  (예: 20%의 경우 0.20 으로 입력)")
    print("=" * 65)

    print("\n▶ [1] 5대 예산 배분 입력 (총합 1.0)")
    welfare = float(input(" - 복지 예산 (welfare)         : "))
    education = float(input(" - 교육 예산 (education)       : "))
    energy_infra = float(input(" - 에너지 인프라 (energy_infra): "))
    general_infra = float(input(" - 일반 인프라 (general_infra) : "))
    safety = float(input(" - 안전 예산 (safety)          : "))

    resource = Resource(welfare, education, energy_infra, general_infra, safety)

    print("\n▶ [2] 4대 에너지원 구성 입력 (총합 1.0)")
    solar = float(input(" - 태양광 발전 (Solar Panel)   : "))
    hydro = float(input(" - 수소연료전지 (Hydrogen Cell): "))
    ess = float(input(" - ESS (에너지 저장장치)       : "))
    ext = float(input(" - 외부 전력망 (External Grid) : "))

    eg = EnergyGrid([
        SolarPanel(solar), HydrogenCell(hydro),
        ESS(ess), ExternalGrid(ext)
    ])

    return resource, eg


def print_result(name: str, result: Dict) -> None:
    print(f"\n  {'─'*63}")
    print(f"  시나리오: 【 {name} 】")
    print(f"  {'─'*63}")
    r = result["resource"]
    print(f"  입력 예산: {r}")
    rate = result["independence_rate"]
    sav  = result["savings"]
    adj  = result["adjusted_budget"]
    print(f"  에너지 자립률: {rate*100:.1f}%  │  절감액: {sav*100:.2f}%  │  에너지보정: {energy_to_bonus(rate):+.1f}점")
    print(f"  조정 예산:  {adj}")
    print(f"\n  {'구역':<18} {'만족도':>7}  {'게이지':>20}  {'평가':>8}")
    print(f"  {'─'*58}")
    for d_name, score in result["districts"].items():
        bar = "█" * int(score/5) + "░" * (20 - int(score/5))
        if score < 50:     ev = "⚠️ 위험"
        elif score < 60:   ev = "주의"
        elif score < 75:   ev = "양호"
        else:              ev = "✅ 우수"
        print(f"  {d_name:<18} {score:>6.1f}점  {bar}  {ev}")
    avg = result["city_average"]
    gap = max(result["districts"].values()) - min(result["districts"].values())
    print(f"\n  {'도시 평균':<18} {avg:>6.1f}점  (구역 간 격차: {gap:.1f}점)")
    if result["warnings"]:
        for w in result["warnings"]:
            print(f"    {w}")


def print_comparison(comp: Dict) -> None:
    change = comp["city_avg_change"]
    arrow = "▲" if change > 0 else "▼"
    print(f"\n  [{comp['scenario_a']}]  →  [{comp['scenario_b']}]")
    print(f"  도시 평균: {change:+.1f}점 {arrow}  │  에너지 자립률: {comp['independence_change']:+.1f}%p  │  절감액: {comp['savings_change']:+.2f}%p")
    print(f"  {'구역별 변화':}")
    for d_name, delta in comp["district_changes"].items():
        arrow2 = "↑" if delta > 0 else "↓" if delta < 0 else "→"
        bar = "█" * min(20, int(abs(delta)))
        print(f"    {d_name:<22}  {arrow2}  {delta:>+6.1f}점  {bar}")


def print_tradeoff_table(results: Dict) -> None:
    d_names = list(list(results.values())[0]["districts"].keys())
    header = f"  {'시나리오':<14}"
    for d in d_names:
        header += f"  {d.split('(')[0]:>7}"
    header += f"  {'평균':>7}  {'자립률':>7}  {'절감액':>7}"
    print(header)
    print("  " + "─" * 82)
    for name, result in results.items():
        short_name = name[:13] + ".." if len(name) > 13 else name
        row = f"  {short_name:<14}"
        for d in d_names:
            row += f"  {result['districts'][d]:>7.1f}"
        row += (f"  {result['city_average']:>7.1f}"
                f"  {result['independence_rate']*100:>6.1f}%"
                f"  {result['savings']*100:>6.2f}%")
        print(row)


def verify_magic_methods() -> None:
    print("\n\n" + "=" * 65)
    print("  【 매직 메서드 + OOP 요건 검증 】")
    print("=" * 65)

    print("\n  ▶ __str__ / __repr__")
    worker = Worker(); elder = Elder()
    print(f"  Worker.__str__: {worker}")
    print(f"  Elder.__str__:  {elder}")
    print(f"  Worker.__repr__: {repr(worker)}")

    print("\n  ▶ __len__  (ESS, District, EnergyGrid)")
    ess  = ESS(0.25)
    print(f"  ESS(25%) len: {len(ess)}  (용량 25)")
    grid = EnergyGrid([SolarPanel(0.40),HydrogenCell(0.35),ESS(0.20),ExternalGrid(0.05)])
    print(f"  EnergyGrid len: {len(grid)}  (에너지원 4종)")

    print("\n  ▶ __add__  (Resource 합산 + 정규화)")
    r1 = Resource(0.20,0.20,0.20,0.20,0.20)
    r2 = Resource.__new__(Resource)
    r2.welfare=0.04; r2.education=0.04; r2.energy_infra=0.0
    r2.general_infra=0.0; r2.safety=0.0
    r3 = r1 + r2
    print(f"  기존:   {r1}")
    print(f"  합산후: {r3}")

    print("\n  ▶ 커스텀 예외 3종 동작 확인")
    try:
        Resource(0.50,0.50,0.50,0.00,0.00)
    except BudgetAllocationError as e:
        print(f"  BudgetAllocationError ✅: {e}")
    try:
        EnergyGrid([SolarPanel(0.50),ExternalGrid(0.80)])
    except EnergyAllocationError as e:
        print(f"  EnergyAllocationError ✅: {e}")

    city = build_nova_city()
    r    = Resource(0.20,0.18,0.30,0.22,0.10)
    eg   = EnergyGrid([SolarPanel(0.40),HydrogenCell(0.35),ESS(0.20),ExternalGrid(0.05)])
    res  = city.apply_policy(r, eg)
    low  = [(d, s) for d, s in res["districts"].items() if s < 50]
    if low:
        for d, s in low:
            print(f"  LowSatisfactionWarning ✅: {d} {s:.1f}점")
    else:
        print("  LowSatisfactionWarning: 이 시나리오에서는 발생 안 함 (정상)")

    print("\n  ▶ EnergyGrid __str__")
    print(f"  {grid}")

    print("\n  ▶ District __str__ (계산 후)")
    for d in city.districts:
        print(f"  {d}")

    print("\n  ▶ PolicySimulator __str__")
    sim = PolicySimulator(city)
    print(f"  {sim}")


def main():
    print("\n" + "=" * 65)
    print("  NOVA시 스마트시티 자원 배분 시뮬레이터  v3.0  (커스텀 전용)")
    print("  Social Science & AI 융합학부  OOP 프로젝트")
    print("=" * 65)

    verify_core_functions()

    print("\n\n" + "=" * 65)
    print("  【 NOVA시 시나리오 시뮬레이션 】")
    print("=" * 65)

    city      = build_nova_city()
    simulator = PolicySimulator(city)
    scenarios = define_scenarios()

    # ---------------------------------------------------------
    # 사용자 입력 시나리오 추가 (예외 처리 포함)
    # ---------------------------------------------------------
    while True:
        try:
            user_resource, user_eg = get_user_scenario()
            scenarios["사용자 커스텀 시나리오"] = (user_resource, user_eg)
            print("\n✅ 사용자 시나리오가 성공적으로 등록되었습니다!")
            break
        except BudgetAllocationError as e:
            print(f"\n❌ [입력 오류] {e}")
            print("예산 비율을 다시 확인하고 입력해 주세요.")
        except EnergyAllocationError as e:
            print(f"\n❌ [입력 오류] {e}")
            print("에너지원 비율을 다시 확인하고 입력해 주세요.")
        except ValueError:
            print("\n❌ [입력 오류] 숫자(소수점) 형식으로만 입력해 주세요.")
    # ---------------------------------------------------------

    results = {}
    for name, (resource, eg) in scenarios.items():
        result = simulator.run(resource, eg, name)
        results[name] = result
        print_result(name, result)

    print("\n\n" + "=" * 65)
    print("  【 구역별 트레이드오프 종합 요약 】")
    print("=" * 65)
    print_tradeoff_table(results)

    verify_magic_methods()

    print(f"\n\n  최종 상태: {simulator}")


if __name__ == "__main__":
    main()