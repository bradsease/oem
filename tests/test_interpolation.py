import datetime as dt
from pathlib import Path

import numpy as np
import pytest
from astropy import units
from astropy.time import Time, TimeDelta

from oem import OrbitEphemerisMessage
from oem.interp import (
    EphemerisInterpolator,
    HermitePolynomial,
    HermiteStateInterpolator,
    LagrangeStateInterpolator,
)

THIS_DIR = Path(__file__).parent
SAMPLE_DIR = THIS_DIR / "samples"


def _make_test_states(poly, t_step, count, accel=True):
    """Create state samples for testing.

    Args:
        poly (poly1d): Polynomial describing position history.
        t_step (float): State time step in seconds.
        count (int): Number of points to sample.
        accel (bool, optional): If True, output States will have accelerations.

    Returns:
        states (list): List of State with position, velocity, and acceleration
            following poly, poly.deriv, and poly.deriv.deriv, respectively.
            Epochs are DateTimes starting at the current time and stepping
            by t_step.
    """
    start_epoch = dt.datetime.now()
    epochs = [
        Time(start_epoch + dt.timedelta(seconds=t_step * idx)) for idx in range(count)
    ]
    positions = [poly([t_step * idx] * 3) for idx in range(count)]
    velocities = [poly.deriv()([t_step * idx] * 3) for idx in range(count)]
    if accel:
        accelerations = [
            poly.deriv().deriv()([t_step * idx] * 3) for idx in range(count)
        ]
        return (epochs, *zip(*positions), *zip(*velocities), *zip(*accelerations))
    else:
        return (epochs, *zip(*positions), *zip(*velocities))


def test_hermite_spice_reference():
    times = np.array([-1.0, 0.0, 3.0, 5.0])
    values = np.array([6.0, 5.0, 2210.0, 78180.0])
    derivatives = np.array([3.0, 0.0, 5115.0, 109395.0])

    value, derivative = HermitePolynomial(times, values, derivatives)(2.0)

    assert value == 141.0
    assert derivative == 456.0


def test_hermite_anise_regression():
    # Regression data from ANISE commit 47220637, validated against SPICE HRMINT.
    epoch = 773064069.1841084
    epochs = np.array(
        [
            773063753.0320327,
            773063842.6860328,
            773063932.1790327,
            773064021.5950327,
            773064111.0160326,
            773064200.4970326,
            773064290.0490326,
            773064379.5660326,
            773064467.8020325,
        ]
    )
    positions = np.array(
        [
            1264.0276092333008,
            1169.380111723055,
            1067.501355281949,
            958.9770086109238,
            844.4072328473662,
            724.4430188794065,
            599.8186349004518,
            471.46623936222625,
            342.04349989730264,
        ]
    )
    velocities = np.array(
        [
            -1.0119972729331588,
            -1.0982621220038147,
            -1.1773202325269372,
            -1.248793644639029,
            -1.3123304769876323,
            -1.3675873394086253,
            -1.414230273831576,
            -1.4519274117465721,
            -1.4801351852184736,
        ]
    )

    position, velocity = HermitePolynomial(epochs, positions, velocities)(epoch)

    assert position == pytest.approx(898.710335153595, abs=1e-8)
    assert velocity == pytest.approx(-1.2836208430532707, abs=1e-10)


def test_newton_hermite_spice_boundary_regression():
    samples = 12
    step = 900.0
    times = np.arange(samples) * step
    angular_rate = 2 * np.pi / 5400.0
    sample_indices = np.arange(samples)
    positions = 7000 * np.cos(angular_rate * times)
    positions += 1e-3 * np.sin(1.7 * sample_indices)
    velocities = -7000 * angular_rate * np.sin(angular_rate * times)
    velocities += 1e-6 * np.cos(2.3 * sample_indices)
    epoch = 256.5

    position, velocity = HermitePolynomial(times, positions, velocities)(epoch)

    assert position == pytest.approx(6690.275044353001, abs=1e-9)
    assert velocity == pytest.approx(-2.3948915947403475, abs=1e-11)


@pytest.mark.parametrize("has_accel", (True, False))
@pytest.mark.parametrize(
    "Interpolator, samples",
    ((LagrangeStateInterpolator, 8), (HermiteStateInterpolator, 4)),
)
def test_interpolators(Interpolator, samples, has_accel):
    position = np.poly1d([0.1, 0.1, 0.1])
    velocity = position.deriv()
    acceleration = velocity.deriv()
    time_step = 60

    states = _make_test_states(position, time_step, samples, accel=has_accel)
    interpolator = Interpolator(states)

    for elapsed in np.arange(0, (samples - 1) * time_step, 1):
        test_epoch = states[0][0] + TimeDelta(elapsed, format="sec")
        predict_pos, predict_vel, predict_accel = interpolator(test_epoch)
        np.testing.assert_almost_equal(predict_pos, position(elapsed))
        np.testing.assert_almost_equal(predict_vel, velocity(elapsed))
        if has_accel:
            np.testing.assert_almost_equal(predict_accel, acceleration(elapsed))


@pytest.mark.parametrize("has_accel", (True, False))
@pytest.mark.parametrize("method, order", (("LAGRANGE", 8), ("HERMITE", 9)))
def test_ephemeris_interpolator(method, order, has_accel):
    position = np.poly1d([0.1, 0.1, 0.1])
    velocity = position.deriv()
    acceleration = velocity.deriv()
    time_step = 30
    samples = 25

    states = _make_test_states(position, time_step, samples, accel=has_accel)
    interpolator = EphemerisInterpolator(states, method, order)

    for elapsed in np.arange(0, (samples - 1) * time_step, 5):
        test_epoch = states[0][0] + TimeDelta(elapsed, format="sec")
        predict_pos, predict_vel, predict_accel = interpolator(test_epoch)
        np.testing.assert_almost_equal(predict_pos, position(elapsed), 6)
        np.testing.assert_almost_equal(predict_vel, velocity(elapsed), 6)
        if has_accel:
            np.testing.assert_almost_equal(predict_accel, acceleration(elapsed), 6)


@pytest.mark.parametrize("method, order", (("HERMITE", 9), ("LAGRANGE", 5)))
def test_ephemeris_interpolator_caches_local_window(method, order):
    states = _make_test_states(np.poly1d([0.1, 0.1, 0.1]), 30, 10, accel=False)
    interpolator = EphemerisInterpolator(states, method, order)

    first = interpolator._get_best_interpolator(states[0][0])
    second = interpolator._get_best_interpolator(
        states[0][0] + TimeDelta(1, format="sec")
    )
    last = interpolator._get_best_interpolator(states[0][-1])
    first_again = interpolator._get_best_interpolator(states[0][0])

    assert second is first
    assert last is not first
    assert first_again is not last


@pytest.mark.parametrize(
    "coarse_file, fine_file",
    (
        ("GEO_60s.oem", "GEO_20s.oem"),
        ("MEO_60s.oem", "MEO_20s.oem"),
        ("LEO_60s.oem", "LEO_10s.oem"),
    ),
)
def test_ephemeris_accuracy(coarse_file, fine_file):
    fine_sample = SAMPLE_DIR / "real" / fine_file
    coarse_sample = SAMPLE_DIR / "real" / coarse_file
    fine_oem = OrbitEphemerisMessage.open(fine_sample)
    coarse_oem = OrbitEphemerisMessage.open(coarse_sample)

    for state in fine_oem.states:
        predict = coarse_oem(state.epoch)
        np.testing.assert_almost_equal(predict.position, state.position, 6)
        np.testing.assert_almost_equal(predict.velocity, state.velocity, 6)
        if state.has_accel:
            np.testing.assert_almost_equal(predict.acceleration, state.acceleration, 6)


@pytest.mark.parametrize("input_file", ("GEO_20s.oem", "MEO_20s.oem", "LEO_10s.oem"))
def test_ephemeris_stepping(input_file):
    sample_file = SAMPLE_DIR / "real" / input_file
    oem = OrbitEphemerisMessage.open(sample_file)

    for state in oem.steps(601):
        assert state.epoch in oem

    for segment in oem:
        for state in segment.steps(601):
            assert state.epoch in oem

    out_of_bounds_epoch = oem.span[0] - TimeDelta(1 * units.day)
    with pytest.raises(ValueError):
        oem(out_of_bounds_epoch)
    for segment in oem:
        with pytest.raises(ValueError):
            segment(out_of_bounds_epoch)


@pytest.mark.parametrize("input_file", ("GEO_20s.oem", "MEO_20s.oem", "LEO_10s.oem"))
def test_ephemeris_resample(input_file):
    sample_file = SAMPLE_DIR / "real" / input_file
    step_size = 600
    oem = OrbitEphemerisMessage.open(sample_file)
    new_oem = oem.resample(step_size)

    for idx in range(1, len(new_oem.states)):
        assert np.isclose(
            (new_oem.states[idx].epoch - new_oem.states[idx - 1].epoch).sec, step_size
        )


@pytest.mark.parametrize("in_place", (True, False))
def test_segment_resample_sampling_uses_resampled_states(in_place, tmp_path):
    sample_file = SAMPLE_DIR / "real" / "LEO_10s.oem"
    oem = OrbitEphemerisMessage.open(sample_file)
    segment = oem.segments[0].resample(400, in_place=in_place)
    epoch = segment.useable_start_time + TimeDelta(1800, format="sec")

    sampled_state = segment(epoch)
    resampled_oem = OrbitEphemerisMessage(oem.header.copy(), [segment])
    output_file = tmp_path / "resampled.oem"
    resampled_oem.save_as(output_file)
    reconstructed_state = OrbitEphemerisMessage.open(output_file)(epoch)

    np.testing.assert_allclose(sampled_state.position, reconstructed_state.position)
    np.testing.assert_allclose(sampled_state.velocity, reconstructed_state.velocity)
