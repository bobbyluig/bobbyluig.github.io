const element = document.getElementById('chart-floor-latency-histogram');
const chart = echarts.init(element, null, { width: 740, height: 380 });
chart.setOption({
  textStyle: {
    fontFamily: 'Roboto',
    fontSize: 16,
  },
  tooltip: {
    trigger: 'axis',
    axisPointer: {
      type: 'shadow'
    },
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
      data: [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180],
      name: 'Latency (s)',
      nameLocation: 'center',
      nameGap: 35,
      axisLabel: {
        fontFamily: 'Roboto',
        fontSize: 16,
      },
    },
  ],
  yAxis: [
    {
      type: 'value',
      name: 'Count',
      nameLocation: 'center',
      nameGap: 60,
      axisLabel: {
        fontFamily: 'Roboto',
        fontSize: 16,
      },
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