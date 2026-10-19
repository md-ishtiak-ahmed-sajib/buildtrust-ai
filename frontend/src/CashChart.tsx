import type { Forecast } from "./types";
import { formatMoney } from "./api";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  LineChart,
  Line,
  Legend,
} from "recharts";
export default function CashChart({
  forecast,
  all = false,
}: {
  forecast: Forecast;
  all?: boolean;
}) {
  const points = forecast.scenarios[0].days.map((d, i) => ({
    date: d.date.slice(5),
    base: Number(d.closing),
    delayed: Number(forecast.scenarios[1].days[i].closing),
    cost: Number(forecast.scenarios[2].days[i].closing),
  }));
  const axes = (
    <>
      <CartesianGrid vertical={false} stroke="#e9eef0" strokeDasharray="4 4" />
      <XAxis
        dataKey="date"
        tickLine={false}
        axisLine={false}
        minTickGap={30}
        tick={{ fontSize: 11, fill: "#78838a" }}
        tickMargin={12}
      />
      <YAxis
        tickLine={false}
        axisLine={false}
        tick={{ fontSize: 11, fill: "#78838a" }}
        tickFormatter={(v) => `${Number(v) / 100000}L`}
        width={48}
      />
      <Tooltip
        formatter={(value) => `BDT ${formatMoney(String(value))}`}
        contentStyle={{
          borderRadius: 10,
          border: "1px solid #e5e9ec",
          fontSize: 12,
        }}
      />
      <ReferenceLine
        y={Number(forecast.minimum_reserve)}
        stroke="#c28b3a"
        strokeDasharray="5 5"
      />
    </>
  );
  return (
    <>
      <div
        className="chart"
        role="img"
        aria-label="30-day cash flow projection; equivalent data in the following table"
      >
        <ResponsiveContainer width="100%" height="100%">
          {all ? (
            <LineChart
              data={points}
              margin={{ top: 10, right: 16, bottom: 4, left: 0 }}
            >
              {axes}
              <Legend
                iconType="plainline"
                wrapperStyle={{ fontSize: 12, paddingTop: 16 }}
              />
              <Line
                isAnimationActive={false}
                dataKey="base"
                name="Base case"
                stroke="#297c72"
                strokeWidth={3}
                dot={false}
              />
              <Line
                isAnimationActive={false}
                dataKey="delayed"
                name="Delayed receivables"
                stroke="#c48c40"
                strokeWidth={2}
                dot={false}
              />
              <Line
                isAnimationActive={false}
                dataKey="cost"
                name="Cost pressure"
                stroke="#6672a5"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          ) : (
            <AreaChart
              data={points}
              margin={{ top: 10, right: 16, bottom: 4, left: 0 }}
            >
              <defs>
                <linearGradient id="cashFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3a8f7e" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#3a8f7e" stopOpacity={0} />
                </linearGradient>
              </defs>
              {axes}
              <Area
                isAnimationActive={false}
                dataKey="base"
                name="Projected cash"
                type="stepAfter"
                stroke="#2e8072"
                strokeWidth={2.5}
                fill="url(#cashFill)"
              />
            </AreaChart>
          )}
        </ResponsiveContainer>
      </div>
      <details className="chart-data">
        <summary>View daily cash flow as a table</summary>
        <div className="table-scroll">
          <table>
            <caption>Projected closing balances in project currency</caption>
            <thead>
              <tr>
                <th scope="col">Date</th>
                {forecast.scenarios.map((s) => (
                  <th scope="col" key={s.name}>
                    {s.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {forecast.scenarios[0].days.map((d, i) => (
                <tr key={d.date}>
                  <th scope="row">{d.date}</th>
                  {forecast.scenarios.map((s) => (
                    <td key={s.name}>{formatMoney(s.days[i].closing)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}
