import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from classes import (
    build_nova_city, PolicySimulator, Resource, EnergyGrid,
    SolarPanel, HydrogenCell, ESS, ExternalGrid, energy_to_bonus
)

# 1. 페이지 설정
st.set_page_config(page_title="NOVA시 스마트시티 대시보드", layout="wide")

st.title("🏙️ NOVA시 스마트시티 자원 배분 시뮬레이터")
st.markdown("예산 배분과 에너지원 구성을 조정하여 도시 만족도를 시뮬레이션하세요.")

# 2. 사이드바: 사용자 입력 (가중치 설정)
st.sidebar.header("🛠️ 정책 설정 (가중치 합계 1.0 필수)")

with st.sidebar.expander("💰 [1] 예산 배분 설정", expanded=True):
    welfare = st.slider("복지", 0.0, 1.0, 0.2, 0.05)
    edu = st.slider("교육", 0.0, 1.0, 0.2, 0.05)
    e_infra = st.slider("에너지 인프라", 0.0, 1.0, 0.2, 0.05)
    g_infra = st.slider("일반 인프라", 0.0, 1.0, 0.2, 0.05)
    safety = st.slider("안전", 0.0, 1.0, 0.2, 0.05)
    
    total_res = round(welfare + edu + e_infra + g_infra + safety, 2)
    st.write(f"**합계: {total_res}**")
    if total_res != 1.0:
        st.error("⚠️ 예산 합계를 1.0으로 맞춰주세요.")

with st.sidebar.expander("⚡ [2] 에너지원 구성 설정", expanded=True):
    solar = st.slider("태양광", 0.0, 1.0, 0.25, 0.05)
    hydro = st.slider("수소연료전지", 0.0, 1.0, 0.25, 0.05)
    ess = st.slider("ESS", 0.0, 1.0, 0.25, 0.05)
    ext = st.slider("외부 전력망", 0.0, 1.0, 0.25, 0.05)
    
    total_eg = round(solar + hydro + ess + ext, 2)
    st.write(f"**합계: {total_eg}**")
    if total_eg != 1.0:
        st.error("⚠️ 에너지 합계를 1.0으로 맞춰주세요.")

# 3. 시뮬레이션 실행 로직
if total_res == 1.0 and total_eg == 1.0:
    # 데이터 준비
    city = build_nova_city() # classes.py에서 정의한 기본 도시 빌드
    simulator = PolicySimulator(city)
    
    resource = Resource(welfare, edu, e_infra, g_infra, safety)
    eg = EnergyGrid([
        SolarPanel(solar), HydrogenCell(hydro), 
        ESS(ess), ExternalGrid(ext)
    ])
    
    # 시뮬레이션 실행
    result = simulator.run(resource, eg, "사용자 시나리오")
    
    # 4. 결과 시각화
    st.divider()
    
    # 상단 요약 지표 (Metrics)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("도시 평균 만족도", f"{result['city_average']:.1f}점")
    col2.metric("에너지 자립률", f"{result['independence_rate']*100:.1f}%")
    col3.metric("예산 절감액", f"{result['savings']*100:.2f}%")
    col4.metric("에너지 보정", f"{energy_to_bonus(result['independence_rate']):+.1f}점")

    # 그래프 레이아웃
    chart_col, table_col = st.columns([2, 1])
    
    with chart_col:
        st.subheader("📊 구역별 만족도 결과")
        df = pd.DataFrame({
            "구역": list(result["districts"].keys()),
            "만족도": list(result["districts"].values())
        })
        st.bar_chart(data=df, x="구역", y="만족도", color="#0078D4")

    with table_col:
        st.subheader("📋 세부 수치")
        st.table(df)

    # 경고창 표시
    if result["warnings"]:
        for w in result["warnings"]:
            st.warning(w)

else:
    st.info("왼쪽 사이드바에서 모든 가중치 합계를 1.0으로 설정하면 시뮬레이션이 시작됩니다.")