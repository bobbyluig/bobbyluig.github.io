const data_fixed = [0, 1, 0, 0, 0, 0, 0, 1, 0, 2, 4, 3, 5, 3, 5, 5, 16, 6, 9, 40];
const data_greedy = [29, 9, 6, 3, 4, 3, 6, 2, 3, 0, 1, 3, 2, 4, 3, 3, 3, 5, 3, 8];
const data_search = [45, 9, 9, 4, 2, 5, 1, 2, 3, 3, 4, 1, 1, 2, 2, 0, 0, 5, 0, 2];
const element = document.getElementById('chart-horizontal');
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
      data: Array.from({ length: 20 }, (_, i) => i * 100),
      name: 'Distance From Target (m)',
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
      nameGap: 45,
      axisLabel: {
        fontFamily: 'Roboto',
        fontSize: 16,
      },
    },
  ],
  series: [
    {
      name: 'Fixed',
      type: 'bar',
      data: data_fixed,
    },
    {
      name: 'Greedy',
      type: 'bar',
      data: data_greedy,
    },
    {
      name: 'Search',
      type: 'bar',
      data: data_search,
    },
  ],
});