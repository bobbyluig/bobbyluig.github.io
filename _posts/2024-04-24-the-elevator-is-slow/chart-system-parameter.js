const element = document.getElementById('chart-system-parameter');
const chart = echarts.init(element, null, { width: 740, height: 380 });
chart.setOption({
  textStyle: {
    fontFamily: 'Roboto',
    fontSize: 16,
  },
  tooltip: {
    trigger: 'axis',
    axisPointer: {
      type: 'shadow',
    },
    valueFormatter: (value) => value.toFixed(3),
    textStyle: {
      fontFamily: 'Roboto',
      fontSize: 16,
    },
  },
  grid: {
    left: 35,
    top: 45,
    right: 5,
    bottom: 30,
    containLabel: true,
  },
  legend: {},
  xAxis: [
    {
      type: 'category',
      data: ['e_vel', 'e_d_vel', 'e_d_wai', 'e_acc', 'p_vel', 'e_cap'],
      name: 'Parameter',
      nameLocation: 'center',
      nameGap: 35,
      axisLabel: {
        fontFamily: 'Roboto',
        fontSize: 16,
      },
    }
  ],
  yAxis: [
    {
      type: 'value',
      name: 'Ratio',
      nameLocation: 'center',
      nameGap: 45,
      axisLabel: {
        fontFamily: 'Roboto',
        fontSize: 16,
      },
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