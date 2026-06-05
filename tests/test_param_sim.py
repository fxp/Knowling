"""param_sim x-sweep: parametric curves (sliders are params, x is the axis) vs
the legacy slider-is-axis pattern."""

from knowling.blocks import param_sim


def _analyze(cs):
    return param_sim._analyze(cs["params"], cs["outputs"], cs)


def test_legacy_slider_is_axis():
    # param x, output x*x → x is a slider AND the axis (drag x, see y=x²)
    cs = {"params": [{"name": "x", "min": 0, "max": 5, "default": 2}],
          "outputs": [{"name": "y", "expr": "x*x"}]}
    sweep, curves, scalars, legacy = _analyze(cs)
    assert legacy is True
    assert sweep["name"] == "x" and sweep["min"] == 0.0 and sweep["max"] == 5.0
    assert curves[0]["expr"] == "x*x"


def test_parametric_curve_detects_sweep_var():
    # sliders A/w/phi, free var x is the horizontal sweep
    cs = {"params": [{"name": "A", "min": -3, "max": 3, "default": 1},
                     {"name": "w", "min": 0.5, "max": 5, "default": 1},
                     {"name": "phi", "min": -3.14, "max": 3.14, "default": 0}],
          "outputs": [{"name": "y", "expr": "A*Math.sin(w*x + phi)"},
                      {"name": "T", "expr": "2*PI/w"}]}
    sweep, curves, scalars, legacy = _analyze(cs)
    assert legacy is False
    assert sweep["name"] == "x"  # x is not a param → it's the sweep
    assert [c["name"] for c in curves] == ["y"]    # mentions x → plotted
    assert [s["name"] for s in scalars] == ["T"]   # over params only → readout


def test_template_embeds_sweep_and_curves():
    cs = {"params": [{"name": "A", "min": -2, "max": 2, "default": 1}],
          "outputs": [{"name": "y", "label": "y", "expr": "A*Math.sin(x)"}]}
    html = param_sim.template({"block_id": "ps", "type": "param_sim", "content_spec": cs})
    assert 'data-block-id="ps"' in html
    assert "A*Math.sin(x)" in html          # curve expr present
    assert '"name": "x"' in html or "'name': 'x'" in html  # sweep wired
    assert "<canvas" in html and 'type="range"' in html


def test_free_vars_ignores_math():
    assert param_sim._free_vars("A*Math.sin(w*x + phi)") == {"A", "w", "x", "phi"}
    assert "Math" not in param_sim._free_vars("Math.cos(x)")
