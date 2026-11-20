// LATFUN6 pinout smoke test: touches every signal in board/latfun6.lpf so place-and-route
// proves the pinout (balls, banks, IO types, LVCMOS33D pairs) on the target device.  MIT licence.
module pinout_smoke (
    input  wire       clk_25mhz,
    output wire [7:0] led,
    input  wire [3:0] btn_n,
    input  wire [3:0] sw_n,
    output wire       uart_tx,
    input  wire       uart_rx,
    output wire       uart_rts_n,
    input  wire       uart_cts_n,
    inout  wire       flash_io2, flash_io3, flash_mosi, flash_miso, flash_cs_n,
    inout  wire       i2c_scl, i2c_sda,
    output wire       audio_l, audio_r,
    output wire       gpdi_clk_p, gpdi_d0_p, gpdi_d1_p, gpdi_d2_p,
    inout  wire       gpdi_scl, gpdi_sda,
    input  wire       gpdi_hpd,
    output wire [7:0] la,
    output wire       tp_pll,
    output wire       loop_a,
    input  wire       loop_b,
    inout  wire [10:1] pmod1, pmod2, pmod3, pmod4
);
    reg [25:0] cnt = 0;
    always @(posedge clk_25mhz) cnt <= cnt + 1;
    wire [7:0] inputs = {~btn_n, ~sw_n} ^ {uart_rx, uart_cts_n, gpdi_hpd, loop_b, 4'b0};
    assign led = cnt[25:18] ^ inputs;
    assign uart_tx = uart_rx;           // echo
    assign uart_rts_n = 1'b0;
    assign {flash_io2, flash_io3} = 2'b11;  // hold WP#/HOLD# high
    assign {flash_mosi, flash_cs_n} = 2'bzz;
    assign flash_miso = 1'bz;
    assign i2c_scl = cnt[10] ? 1'bz : 1'b0;   // open drain
    assign i2c_sda = 1'bz;
    assign gpdi_scl = 1'bz;
    assign gpdi_sda = 1'bz;
    assign audio_l = cnt[3];
    assign audio_r = cnt[4];
    assign {gpdi_clk_p, gpdi_d0_p, gpdi_d1_p, gpdi_d2_p} = cnt[3:0];
    assign la = cnt[7:0];
    assign tp_pll = cnt[0];
    assign loop_a = cnt[20];
    genvar i;
    generate for (i = 1; i <= 10; i = i + 1) begin : g
        if (i != 5 && i != 6) begin    // pins 5/6 and 11/12 of a PMOD are GND/3V3
            assign pmod1[i] = cnt[i];
            assign pmod2[i] = cnt[i+1];
            assign pmod3[i] = cnt[i+2];
            assign pmod4[i] = cnt[i+3];
        end
    end endgenerate
endmodule
