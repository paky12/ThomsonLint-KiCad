from kicad.analyzers.net_classifier import classify_net, classify_component, NetClassification


class TestPowerNets:
    def test_vcc(self):
        r = classify_net("VCC")
        assert r.is_power is True
        assert r.is_ground is False

    def test_vdd_3v3(self):
        r = classify_net("+3V3")
        assert r.is_power is True
        assert r.voltage_guess == "3.3V"

    def test_vbus(self):
        r = classify_net("VBUS")
        assert r.is_power is True
        assert r.voltage_guess == "5V"

    def test_vbat(self):
        r = classify_net("VBAT")
        assert r.is_power is True
        assert r.voltage_guess == "3.7V"

    def test_5v0(self):
        r = classify_net("5V0")
        assert r.is_power is True
        assert r.voltage_guess == "5V"

    def test_case_insensitive(self):
        r = classify_net("vcc_mcu")
        assert r.is_power is True

    def test_plus_3_3v(self):
        cl = classify_net("+3.3V")
        assert cl.is_power

    def test_vref_plus(self):
        cl = classify_net("VREF+")
        assert cl.is_power

    def test_vdda(self):
        cl = classify_net("VDDA")
        assert cl.is_power


class TestGroundNets:
    def test_gnd(self):
        r = classify_net("GND")
        assert r.is_ground is True

    def test_agnd(self):
        r = classify_net("AGND")
        assert r.is_ground is True

    def test_contains_gnd(self):
        r = classify_net("PWR_GND")
        assert r.is_ground is True

    def test_vss(self):
        r = classify_net("DVSS")
        assert r.is_ground is True


class TestClockNets:
    def test_clk(self):
        r = classify_net("SYS_CLK")
        assert r.is_clock is True

    def test_xtal(self):
        r = classify_net("XTAL_IN")
        assert r.is_clock is True

    def test_sclk(self):
        r = classify_net("SPI_SCLK")
        assert r.is_clock is True

    def test_osc(self):
        r = classify_net("OSC_OUT")
        assert r.is_clock is True

    def test_not_clock(self):
        r = classify_net("DATA_IN")
        assert r.is_clock is False


class TestDiffPairs:
    def test_positive_p(self):
        r = classify_net("USB_D_P")
        assert r.is_differential is True
        assert r.diff_polarity == 1
        assert r.diff_pair_partner == "USB_D_N"

    def test_negative_n(self):
        r = classify_net("USB_D_N")
        assert r.is_differential is True
        assert r.diff_polarity == -1
        assert r.diff_pair_partner == "USB_D_P"

    def test_dp_suffix(self):
        r = classify_net("ETH_TDP")
        assert r.is_differential is True
        assert r.diff_pair_partner == "ETH_TDN"

    def test_dplus(self):
        r = classify_net("USB_D+")
        assert r.is_differential is True
        assert r.diff_pair_partner == "USB_D-"

    def test_not_differential(self):
        r = classify_net("DATA")
        assert r.is_differential is False
        assert r.diff_pair_partner is None


class TestInterfaceGuess:
    def test_usb(self):
        r = classify_net("USB_D_P")
        assert r.interface_guess == "USB"

    def test_ethernet(self):
        r = classify_net("ETH_TDP")
        assert r.interface_guess == "Ethernet"

    def test_pcie(self):
        r = classify_net("PCIE_TX_P")
        assert r.interface_guess == "PCIe"

    def test_unknown(self):
        r = classify_net("SOME_SIGNAL_P")
        assert r.interface_guess == "unknown"


class TestVoltageGuess:
    def test_3v3(self):
        assert classify_net("3V3_MCU").voltage_guess == "3.3V"

    def test_1v8(self):
        assert classify_net("1V8_CORE").voltage_guess == "1.8V"

    def test_12v(self):
        assert classify_net("12V_IN").voltage_guess == "12V"

    def test_no_voltage(self):
        assert classify_net("DATA").voltage_guess is None


class TestClassifyComponent:
    def test_ic(self):
        assert classify_component("U1", "") == "IC"

    def test_capacitor(self):
        assert classify_component("C10", "") == "capacitor"

    def test_resistor(self):
        assert classify_component("R5", "") == "resistor"

    def test_led(self):
        assert classify_component("D3", "Green LED 0402") == "LED"

    def test_tvs(self):
        assert classify_component("D1", "TVS Diode 5V") == "TVS"

    def test_zener(self):
        assert classify_component("D2", "Zener 3.3V") == "zener"

    def test_diode_default(self):
        assert classify_component("D4", "Schottky") == "diode"

    def test_ferrite_bead_before_fuse(self):
        assert classify_component("FB1", "") == "ferrite_bead"

    def test_test_point_before_transformer(self):
        assert classify_component("TP1", "") == "test_point"

    def test_fuse(self):
        assert classify_component("F1", "") == "fuse"

    def test_transformer(self):
        assert classify_component("T1", "") == "transformer"

    def test_switch(self):
        assert classify_component("SW1", "") == "switch"

    def test_battery(self):
        assert classify_component("BT1", "") == "battery"

    def test_connector(self):
        assert classify_component("J5", "") == "connector"

    def test_crystal(self):
        assert classify_component("Y1", "") == "crystal"
        assert classify_component("X1", "") == "crystal"

    def test_unknown(self):
        assert classify_component("Z1", "") == "other"
