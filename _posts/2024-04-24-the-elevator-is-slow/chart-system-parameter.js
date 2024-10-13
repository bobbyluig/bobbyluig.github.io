const chart = echarts.init(document.getElementById('chart-system-parameter'));
chart.setOption({
  tooltip: {
    trigger: 'axis',
    axisPointer: {
      type: 'shadow',
    },
    valueFormatter: (value) => value.toFixed(3),
  },
  grid: {
    left: 30,
    top: 40,
    right: 10,
    bottom: 25,
    containLabel: true,
  },
  legend: {},
  xAxis: [
    {
      type: 'category',
      data: ['e_vel', 'e_d_vel', 'e_d_wai', 'e_acc', 'p_vel', 'e_cap'],
      name: 'Parameter',
      nameLocation: 'center',
      nameGap: 30,
    }
  ],
  yAxis: [
    {
      type: 'value',
      name: 'Ratio',
      nameLocation: 'center',
      nameGap: 35,
    },
  ],
  series: [
    {
      name: 'Ratio',
      type: 'bar',
      data: [
        37.8393639353616 / 55.29700344923757,
        47.448846883705926 / 55.29700344923757,
        49.923684426869826 / 55.29700344923757,
        50.897573266073756 / 55.29700344923757,
        53.39151825313947 / 55.29700344923757,
        55.29700344923757 / 55.29700344923757,
      ],
    }
  ]
});