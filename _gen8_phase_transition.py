#!/usr/bin/env python3
"""
Gen 8 — Total Force Transition Model for an asymmetric capacitor.

This standalone script bridges two regimes:
  1. Gen 6: macroscopic EHD / ionic-wind thrust in air
  2. Gen 7: pressure-independent Abraham-force vacuum floor

Model:
    F_total(P, f) = F_EHD(P) + F_A(f)

Assumptions
-----------
* `F_EHD` uses an Ianconescu/Deutsch-inspired wire-to-collector scaling with
  the correct geometry dependence and an order-unity prefactor.
* Pressure roll-off uses a simple mean-free-path knee:
      F_EHD(P) ~ constant                 for P >= 1 Torr
      F_EHD(P) ~ P                        for P < 1 Torr
* `F_A` uses the phenomenological pulsed-voltage relation provided in the prompt:
      F_A ~= 1e-7 * (2 C omega / R) * (DeltaV)^2

The result is a dual-axis log-log plot against pressure, plus a short textual
interpretation of the detectability gap.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

EPS0 = 8.8541878128e-12  # vacuum permittivity [F/m]
DEFAULT_COMPARISON_FREQS_HZ = np.array([1.0e3, 1.0e4, 1.0e5, 1.0e6])


def wire_collector_capacitance(radius_m: float, gap_m: float, length_m: float) -> float:
    """Approximate wire-to-collector capacitance using a cylindrical log factor."""
    if radius_m <= 0 or gap_m <= radius_m or length_m <= 0:
        raise ValueError("Require length > 0 and gap > radius > 0.")
    return 2.0 * np.pi * EPS0 * length_m / np.log(gap_m / radius_m)


def ehd_force_at_1atm(radius_m: float, gap_m: float, length_m: float, voltage_v: float) -> float:
    """Ianconescu/Deutsch-inspired EHD thrust scale at atmospheric density."""
    geom = np.log(gap_m / radius_m)
    return EPS0 * length_m * voltage_v**2 / (gap_m * geom**2)


def pressure_scaling(pressure_torr: np.ndarray, knee_torr: float = 1.0) -> np.ndarray:
    """Simple mean-free-path model: linear below the knee, saturated above it."""
    pressure_torr = np.asarray(pressure_torr, dtype=float)
    return np.minimum(1.0, pressure_torr / knee_torr)


def ehd_force_curve(
    pressure_torr: np.ndarray,
    radius_m: float,
    gap_m: float,
    length_m: float,
    voltage_v: float,
    knee_torr: float = 1.0,
) -> np.ndarray:
    baseline = ehd_force_at_1atm(radius_m, gap_m, length_m, voltage_v)
    return baseline * pressure_scaling(pressure_torr, knee_torr=knee_torr)


def abraham_force(
    freq_hz: float,
    capacitance_f: float,
    delta_v: float,
    series_resistance_ohm: float,
) -> float:
    """Pressure-independent Abraham-force floor from the supplied formula."""
    omega = 2.0 * np.pi * max(freq_hz, 0.0)
    return 1.0e-7 * (2.0 * capacitance_f * omega / series_resistance_ohm) * delta_v**2


def crossover_pressure_torr(
    fehd_atm: float,
    fa: float,
    pressure_knee_torr: float,
) -> float | None:
    """Pressure where F_EHD(P) == F_A, assuming the crossover occurs below the knee."""
    if fa <= 0:
        return None
    if fa >= fehd_atm:
        return pressure_knee_torr
    return pressure_knee_torr * fa / fehd_atm


def detectability_pressure_torr(
    fehd_atm: float,
    sensor_floor_n: float,
    pressure_knee_torr: float,
) -> float | None:
    """Pressure where the EHD-dominated total force falls below a sensor threshold."""
    if sensor_floor_n <= 0:
        return None
    if sensor_floor_n >= fehd_atm:
        return pressure_knee_torr
    return pressure_knee_torr * sensor_floor_n / fehd_atm


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gen 8 asymmetric-capacitor phase-transition simulation")
    parser.add_argument("--radius-mm", type=float, default=0.1, help="Emitter wire radius a [mm]")
    parser.add_argument("--gap-cm", type=float, default=5.0, help="Electrode gap b [cm]")
    parser.add_argument("--length-m", type=float, default=0.3, help="Electrode length l [m]")
    parser.add_argument("--voltage-kv", type=float, default=30.0, help="Applied voltage V [kV]")
    parser.add_argument("--freq-hz", type=float, default=1.0e6, help="Highlight frequency for crossover annotation [Hz]")
    parser.add_argument(
        "--series-resistance-ohm",
        type=float,
        default=1.0e6,
        help="Effective pulsed-drive series resistance R [Ohm] used in the Abraham term",
    )
    parser.add_argument("--pressure-max-torr", type=float, default=760.0, help="Maximum pressure [Torr]")
    parser.add_argument("--pressure-min-torr", type=float, default=1.0e-6, help="Minimum pressure [Torr]")
    parser.add_argument("--pressure-knee-torr", type=float, default=1.0, help="Pressure knee separating saturated and linear EHD response [Torr]")
    parser.add_argument("--sensor-floor-n", type=float, default=1.0e-6, help="Nominal conventional sensor floor [N]")
    parser.add_argument("--points", type=int, default=500, help="Number of pressure samples")
    parser.add_argument("--output", type=str, default="gen8_phase_transition.png", help="Output figure path")
    parser.add_argument("--no-show", action="store_true", help="Skip interactive plot display")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    radius_m = args.radius_mm * 1.0e-3
    gap_m = args.gap_cm * 1.0e-2
    length_m = args.length_m
    voltage_v = args.voltage_kv * 1.0e3

    pressures = np.geomspace(args.pressure_min_torr, args.pressure_max_torr, args.points)

    capacitance_f = wire_collector_capacitance(radius_m, gap_m, length_m)
    fehd_atm = ehd_force_at_1atm(radius_m, gap_m, length_m, voltage_v)
    fehd = ehd_force_curve(
        pressures,
        radius_m,
        gap_m,
        length_m,
        voltage_v,
        knee_torr=args.pressure_knee_torr,
    )

    fa_highlight = abraham_force(args.freq_hz, capacitance_f, voltage_v, args.series_resistance_ohm)
    ftotal_highlight = fehd + fa_highlight

    freq_lines = sorted(set([*DEFAULT_COMPARISON_FREQS_HZ.tolist(), float(args.freq_hz)]))
    fa_lines = {freq: abraham_force(freq, capacitance_f, voltage_v, args.series_resistance_ohm) for freq in freq_lines}

    p_cross = crossover_pressure_torr(fehd_atm, fa_highlight, args.pressure_knee_torr)
    p_detect = detectability_pressure_torr(fehd_atm, args.sensor_floor_n, args.pressure_knee_torr)

    fig, ax_force = plt.subplots(figsize=(11, 7))
    ax_floor = ax_force.twinx()

    ax_force.loglog(pressures, fehd, color="black", linewidth=2.4, label=r"$F_{EHD}(P)$")
    ax_force.loglog(
        pressures,
        ftotal_highlight,
        color="tab:blue",
        linewidth=2.6,
        label=fr"$F_{{total}}(P)$ at $f={args.freq_hz/1e3:.0f}$ kHz",
    )

    colors = plt.cm.plasma(np.linspace(0.15, 0.9, len(freq_lines)))
    for color, freq in zip(colors, freq_lines):
        fa_val = fa_lines[freq]
        if fa_val <= 0:
            continue
        ax_floor.loglog(
            pressures,
            np.full_like(pressures, fa_val),
            linestyle="--",
            linewidth=1.6,
            color=color,
            alpha=0.9,
            label=fr"$F_A$ floor ({freq/1e3:.0f} kHz)",
        )

    if p_detect is not None and args.pressure_min_torr <= p_detect <= args.pressure_max_torr:
        x0 = max(args.pressure_min_torr, min(p_detect, args.pressure_max_torr))
        x1 = args.pressure_min_torr
        ax_force.axvspan(min(x0, x1), max(x0, x1), color="gold", alpha=0.12)
        ax_force.text(
            p_detect,
            args.sensor_floor_n * 1.8,
            "Detectability gap\n(< conventional µN sensor floor)",
            fontsize=9,
            color="darkgoldenrod",
            ha="right",
            va="bottom",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="goldenrod", alpha=0.85),
        )
        ax_force.axhline(args.sensor_floor_n, color="gray", linestyle=":", linewidth=1.2, label="1 µN sensor floor")

    if p_cross is not None and args.pressure_min_torr <= p_cross <= args.pressure_max_torr:
        ax_force.scatter([p_cross], [fa_highlight], color="crimson", s=55, zorder=5)
        ax_force.annotate(
            (
                "Crossover point\n"
                + fr"$P \approx {p_cross:.2e}$ Torr"
                + "\n"
                + fr"$F \approx {fa_highlight:.2e}$ N"
            ),
            xy=(p_cross, fa_highlight),
            xytext=(0.08, 0.16),
            textcoords="axes fraction",
            arrowprops=dict(arrowstyle="->", color="crimson", lw=1.5),
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="crimson", alpha=0.9),
            fontsize=10,
            color="crimson",
        )

    ax_force.set_title("Gen 8 Phase Transition: EHD Thrust to Abraham Vacuum Floor", pad=12)
    ax_force.set_xlabel("Pressure (Torr)")
    ax_force.set_ylabel("Force (N) — macroscopic EHD + total")
    ax_floor.set_ylabel("Force (N) — Abraham floor zoom")

    ax_force.grid(True, which="both", linestyle=":", linewidth=0.7, alpha=0.65)
    ax_force.set_xlim(args.pressure_max_torr, args.pressure_min_torr)

    y_min = min(np.min(ftotal_highlight), min((v for v in fa_lines.values() if v > 0), default=np.min(ftotal_highlight)))
    y_max = max(np.max(fehd), np.max(ftotal_highlight))
    ax_force.set_ylim(max(y_min / 4.0, 1.0e-14), y_max * 4.0)

    positive_fa = [v for v in fa_lines.values() if v > 0]
    if positive_fa:
        ax_floor.set_ylim(max(min(positive_fa) / 3.0, 1.0e-14), max(positive_fa) * 30.0)
        ax_floor.set_yscale("log")

    lines = ax_force.get_lines() + ax_floor.get_lines()
    labels = [line.get_label() for line in lines]
    ax_force.legend(lines, labels, loc="upper right", fontsize=9)

    summary = (
        f"C = {capacitance_f*1e12:.2f} pF | "
        f"F_EHD(1 atm) = {fehd_atm:.3e} N | "
        f"F_A({args.freq_hz/1e3:.0f} kHz) = {fa_highlight:.3e} N"
    )
    fig.text(0.02, 0.02, summary, fontsize=9)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(output_path, dpi=220, bbox_inches="tight")

    print("=== Gen 8 Phase Transition Summary ===")
    print(f"Geometry: a={args.radius_mm:.3f} mm, b={args.gap_cm:.3f} cm, l={args.length_m:.3f} m")
    print(f"Electrical: V={args.voltage_kv:.1f} kV, f={args.freq_hz:.3e} Hz, R={args.series_resistance_ohm:.3e} Ohm")
    print(f"Capacitance estimate: {capacitance_f:.3e} F")
    print(f"EHD thrust at atmospheric pressure: {fehd_atm:.3e} N")
    print(f"Abraham force floor at {args.freq_hz:.3e} Hz: {fa_highlight:.3e} N")
    if p_cross is not None:
        print(f"Crossover pressure: {p_cross:.3e} Torr")
    else:
        print("Crossover pressure: not defined for zero Abraham floor")
    if p_detect is not None:
        print(f"1 µN detectability threshold reached near: {p_detect:.3e} Torr")

    print("\nInterpretation:")
    print("- At high pressure, ion-neutral collisions sustain the EHD / ionic-wind thrust.")
    print("- Below the ~1 Torr mean-free-path knee, the air-mediated force collapses roughly linearly with pressure.")
    print(
        "- The Abraham contribution stays non-zero and pressure-independent, but it sits many orders of magnitude below the air-driven thrust."
    )
    print(
        "- The detectability gap is the vacuum interval where the model predicts a real force floor, yet the signal is typically below conventional micro-Newton instrumentation."
    )
    print(f"\nSaved plot to: {output_path.resolve()}")

    if not args.no_show:
        plt.show()

    plt.close(fig)


if __name__ == "__main__":
    main()
