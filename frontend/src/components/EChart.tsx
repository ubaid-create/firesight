import { useEffect, useRef } from "react";
import * as echarts from "echarts";

type Props = {
  option: any;
  height?: number | string;
  onClick?: (p: any) => void;
};

export const AXIS = {
  axisLine: { lineStyle: { color: "#2d3a4a" } },
  axisTick: { lineStyle: { color: "#2d3a4a" } },
  axisLabel: { color: "#8d9bad", fontSize: 11 },
  splitLine: { lineStyle: { color: "#1a232e" } },
  nameTextStyle: { color: "#8d9bad", fontSize: 11 },
};

export const TOOLTIP = {
  backgroundColor: "#121922",
  borderColor: "#2d3a4a",
  textStyle: { color: "#e4eaf1", fontSize: 12 },
  extraCssText: "border-radius:8px;box-shadow:0 6px 24px rgba(0,0,0,.45);",
};

export const LEGEND = { textStyle: { color: "#aab6c5", fontSize: 11.5 }, itemWidth: 14, itemHeight: 8, top: 0, left: 50, right: 10 };

export default function EChart({ option, height = 300, onClick }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const clickRef = useRef(onClick);
  clickRef.current = onClick;

  useEffect(() => {
    if (!ref.current) return;
    const c = echarts.init(ref.current, undefined, { renderer: "canvas" });
    chart.current = c;
    c.on("click", (p) => clickRef.current && clickRef.current(p));
    const ro = new ResizeObserver(() => c.resize());
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      c.dispose();
    };
  }, []);

  useEffect(() => {
    if (!chart.current || !option) return;
    try {
      chart.current.setOption({ backgroundColor: "transparent", animation: false, ...option }, true);
    } catch (err) {
      console.error("chart render failed", err);
    }
  }, [option]);

  return <div ref={ref} style={{ width: "100%", height }} />;
}
