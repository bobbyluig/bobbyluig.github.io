const chart = echarts.init(document.getElementById('chart-floor-latency-histogram'));
chart.setOption({
  tooltip: {
    trigger: 'axis',
    axisPointer: {
      type: 'shadow'
    },
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
      data: [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180],
      name: 'Latency (s)',
      nameLocation: 'center',
      nameGap: 30,
    },
  ],
  yAxis: [
    {
      type: 'value',
      name: 'Count',
      nameLocation: 'center',
      nameGap: 50,
    },
  ],
  series: [
    {
      name: 'Floor 4',
      type: 'bar',
      data: [4, 1636, 1453, 974, 463, 237, 121, 53, 36, 8, 5, 6, 4, 0, 0, 0, 0, 0]
    },
    {
      name: 'Floor 12',
      type: 'bar',
      data: [0, 2, 1014, 1364, 1153, 638, 342, 217, 131, 73, 39, 15, 9, 1, 2, 0, 0, 0]
    },
    {
      name: 'Floor 20',
      type: 'bar',
      data: [0, 0, 0, 659, 846, 923, 995, 538, 428, 233, 177, 98, 42, 36, 20, 2, 2, 1]
    }
  ]
});