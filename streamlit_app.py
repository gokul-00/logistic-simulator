import streamlit as st
import random
import math

# -----------------------------
# Constants / Game Parameters
# -----------------------------
ORDERS_PER_DAY_BASE = 12000

PETROL_CAPACITY_PER_VEHICLE = 60    # deliveries per day
EV_CAPACITY_PER_VEHICLE = 50        # deliveries per day

PETROL_COST_PER_DEL = 55            # ₹ per successful delivery
EV_COST_PER_DEL = 45                # ₹ per successful delivery
MICRO_HUB_COST_PER_DAY = 8000       # ₹ fixed cost per micro-hub

PETROL_CO2_PER_DEL = 0.8            # kg CO2 per delivery
EV_CO2_PER_DEL = 0.25               # kg CO2 per delivery

BASE_ON_TIME_RATE = 0.80            # 80%
MICRO_HUB_ON_TIME_BOOST = 0.04      # +4 percentage points per hub
EV_ON_TIME_BONUS_THRESHOLD = 0.40   # if EV share >= 40%
EV_ON_TIME_BONUS = 0.02             # +2 percentage points

MAX_DAYS = 5

# -----------------------------
# Helper functions
# -----------------------------
def init_game_state():
    st.session_state.day = 1
    st.session_state.history = []  # list of dicts per day
    st.session_state.game_over = False


def random_event(day):
    """Return a random daily event that affects operations."""
    events = [
        {
            "name": "Clear Day",
            "desc": "Smooth operations, no disruptions.",
            "demand_factor": 1.0,
            "petrol_capacity_factor": 1.0,
            "ev_capacity_factor": 1.0,
            "on_time_penalty": 0.0
        },
        {
            "name": "Heavy Rain",
            "desc": "Traffic is slow; fewer deliveries per vehicle.",
            "demand_factor": 1.0,
            "petrol_capacity_factor": 0.9,
            "ev_capacity_factor": 0.9,
            "on_time_penalty": 0.05
        },
        {
            "name": "Power Cut",
            "desc": "EV charging issues; EV capacity drops.",
            "demand_factor": 1.0,
            "petrol_capacity_factor": 1.0,
            "ev_capacity_factor": 0.5,
            "on_time_penalty": 0.02
        },
        {
            "name": "Festival Demand Surge",
            "desc": "Orders spike by 20%.",
            "demand_factor": 1.2,
            "petrol_capacity_factor": 1.0,
            "ev_capacity_factor": 1.0,
            "on_time_penalty": 0.03
        },
        {
            "name": "Traffic Restrictions",
            "desc": "Some roads closed; overall capacity down 15%.",
            "demand_factor": 1.0,
            "petrol_capacity_factor": 0.85,
            "ev_capacity_factor": 0.85,
            "on_time_penalty": 0.04
        },
    ]
    # deterministic-ish randomness per day
    random.seed(day * 111)
    return random.choice(events)


def simulate_day(day, num_petrol, num_ev, ev_share_percent, num_micro_hubs):
    """Simulate one day of operations based on decisions."""
    # Clamp inputs
    num_petrol = max(0, int(num_petrol))
    num_ev = max(0, int(num_ev))
    ev_share = max(0.0, min(ev_share_percent / 100.0, 1.0))
    num_micro_hubs = max(0, int(num_micro_hubs))

    # Demand and event
    event = random_event(day)
    demand = int(ORDERS_PER_DAY_BASE * event["demand_factor"])

    # Effective capacities
    petrol_capacity = num_petrol * PETROL_CAPACITY_PER_VEHICLE * event["petrol_capacity_factor"]
    ev_capacity = num_ev * EV_CAPACITY_PER_VEHICLE * event["ev_capacity_factor"]

    total_capacity = petrol_capacity + ev_capacity

    # Total deliveries limited by demand and capacity
    deliveries = min(demand, int(total_capacity))
    undelivered = max(0, demand - deliveries)

    # Assign deliveries to EV vs Petrol based on EV share and capacity
    target_ev_deliveries = int(deliveries * ev_share)
    ev_deliveries = min(target_ev_deliveries, int(ev_capacity))
    petrol_deliveries = deliveries - ev_deliveries

    # Costs
    variable_cost = (petrol_deliveries * PETROL_COST_PER_DEL) + (ev_deliveries * EV_COST_PER_DEL)
    fixed_cost = num_micro_hubs * MICRO_HUB_COST_PER_DAY
    total_cost = variable_cost + fixed_cost
    cost_per_order = total_cost / deliveries if deliveries > 0 else 0

    # Emissions
    total_co2 = (petrol_deliveries * PETROL_CO2_PER_DEL) + (ev_deliveries * EV_CO2_PER_DEL)
    co2_per_order = total_co2 / deliveries if deliveries > 0 else 0

    # On-time %
    on_time = BASE_ON_TIME_RATE
    on_time += num_micro_hubs * MICRO_HUB_ON_TIME_BOOST

    # EV bonus for reliability
    ev_actual_share = ev_deliveries / deliveries if deliveries > 0 else 0
    if ev_actual_share >= EV_ON_TIME_BONUS_THRESHOLD:
        on_time += EV_ON_TIME_BONUS

    # Event penalty
    on_time -= event["on_time_penalty"]

    # Capacity stress penalty (if capacity very tight vs demand)
    capacity_ratio = total_capacity / demand if demand > 0 else 1
    if capacity_ratio < 1.0:
        on_time -= (1.0 - capacity_ratio) * 0.10  # up to -10 percentage points

    # Clamp on_time between 0 and 0.99
    on_time = max(0.0, min(on_time, 0.99))

    # Compute a daily efficiency score (0–100)
    # Target benchmarks: cost_per_order ~55, co2_per_order ~0.8, on_time ~0.95
    if deliveries > 0:
        cost_score = max(0, 100 - max(0, cost_per_order - 55) * 2)
        co2_score = max(0, 100 - max(0, co2_per_order - 0.8) * 80)
        on_time_score = max(0, min(100, (on_time / 0.95) * 100))
    else:
        cost_score = 0
        co2_score = 0
        on_time_score = 0

    # Penalty for undelivered orders
    service_penalty = min(30, undelivered / 200.0)  # up to -30

    efficiency_score = (cost_score * 0.3 + co2_score * 0.3 + on_time_score * 0.4) - service_penalty
    efficiency_score = max(0, min(100, efficiency_score))

    results = {
        "day": day,
        "demand": demand,
        "deliveries": deliveries,
        "undelivered": undelivered,
        "num_petrol": num_petrol,
        "num_ev": num_ev,
        "ev_share": ev_actual_share,
        "num_micro_hubs": num_micro_hubs,
        "total_cost": total_cost,
        "cost_per_order": cost_per_order,
        "total_co2": total_co2,
        "co2_per_order": co2_per_order,
        "on_time": on_time,
        "efficiency_score": efficiency_score,
        "event_name": event["name"],
        "event_desc": event["desc"]
    }

    return results


# -----------------------------
# Streamlit App Layout
# -----------------------------
st.set_page_config(page_title="Flipkart Last-Mile Simulator", layout="wide")

st.title("📦 Flipkart: Last-Mile Logistics Simulator")
st.caption("You are the logistics manager of a Tier-II city. Make daily decisions and balance cost, on-time delivery, and emissions.")

# Initialize game state
if "day" not in st.session_state:
    init_game_state()

# Sidebar controls
st.sidebar.header("Game Controls")

if st.sidebar.button("🔄 Reset Game", type="primary"):
    init_game_state()
    st.experimental_rerun()

st.sidebar.markdown(f"### 📅 Day: *{st.session_state.day} / {MAX_DAYS}*")

st.sidebar.write("Make your decisions for *today's operations*:")

num_petrol = st.sidebar.slider("Number of petrol bikes", min_value=0, max_value=200, value=80, step=5)
num_ev = st.sidebar.slider("Number of EV scooters", min_value=0, max_value=200, value=40, step=5)
ev_share_percent = st.sidebar.slider("Target % of deliveries by EV", min_value=0, max_value=100, value=40, step=5)
num_micro_hubs = st.sidebar.slider("Number of micro-hubs to operate", min_value=0, max_value=5, value=2, step=1)

st.sidebar.info(
    "Tip: Try shifting more volume to EVs while keeping enough capacity. "
    "Micro-hubs improve on-time performance but add fixed costs."
)

# Main panel
if st.session_state.day > MAX_DAYS:
    st.header("🎮 Game Over")
    st.write("You have completed all days. Check your overall performance below.")

    if st.session_state.history:
        avg_score = sum(d["efficiency_score"] for d in st.session_state.history) / len(st.session_state.history)
        avg_on_time = sum(d["on_time"] for d in st.session_state.history) / len(st.session_state.history)
        avg_cost = sum(d["cost_per_order"] for d in st.session_state.history) / len(st.session_state.history)
        avg_co2 = sum(d["co2_per_order"] for d in st.session_state.history) / len(st.session_state.history)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Overall Efficiency Score", f"{avg_score:.1f} / 100")
        col2.metric("Avg On-time Delivery", f"{avg_on_time*100:.1f} %")
        col3.metric("Avg Cost per Order", f"₹ {avg_cost:,.1f}")
        col4.metric("Avg CO₂ per Order", f"{avg_co2:.2f} kg")

        st.subheader("Daily Summary")
        st.dataframe(st.session_state.history)
    st.stop()

st.header(f"📅 Day {st.session_state.day}: Plan Your Operations")

st.write(
    "Flipkart expects around *12,000 orders per day* in this Tier-II city. "
    "Demand, traffic, and weather will vary daily. Choose your fleet and micro-hubs, "
    "then click *Run Simulation* to see outcomes."
)

if st.button("▶ Run Today's Simulation", type="primary"):
    day = st.session_state.day
    results = simulate_day(day, num_petrol, num_ev, ev_share_percent, num_micro_hubs)

    # Save history
    st.session_state.history.append(results)
    st.session_state.day += 1

    st.subheader(f"Results for Day {day}")

    st.markdown(f"*Event of the Day:* {results['event_name']} – {results['event_desc']}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Demand (orders)", f"{results['demand']:,}")
    col2.metric("Delivered", f"{results['deliveries']:,}")
    col3.metric("Undelivered", f"{results['undelivered']:,}")

    col4, col5, col6 = st.columns(3)
    col4.metric("Total Cost", f"₹ {results['total_cost']:,.0f}")
    col5.metric("Cost per Order", f"₹ {results['cost_per_order']:,.1f}")
    col6.metric("Efficiency Score", f"{results['efficiency_score']:.1f} / 100")

    col7, col8, col9 = st.columns(3)
    col7.metric("On-time Delivery", f"{results['on_time']*100:.1f} %")
    col8.metric("Total CO₂ Emitted", f"{results['total_co2']:.1f} kg")
    col9.metric("CO₂ per Order", f"{results['co2_per_order']:.2f} kg")

    st.markdown("---")
    st.markdown("### 📊 Operational Breakdown")

    st.write(f"- Petrol bikes used: *{results['num_petrol']}*")
    st.write(f"- EV scooters used: *{results['num_ev']}*")
    st.write(f"- Micro-hubs operated: *{results['num_micro_hubs']}*")
    st.write(f"- Actual EV share of deliveries: *{results['ev_share']*100:.1f}%*")

    st.markdown("### 📈 Progress So Far")
    if st.session_state.history:
        avg_score = sum(d["efficiency_score"] for d in st.session_state.history) / len(st.session_state.history)
        st.write(f"Average efficiency score across {len(st.session_state.history)} day(s): *{avg_score:.1f}/100*")

        # Show table
        st.dataframe(st.session_state.history)

else:
    st.info("Adjust the sliders in the sidebar, then click *Run Today's Simulation* to play this round.")