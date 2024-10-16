const element = document.getElementById('chart-elevator-count');
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
    valueFormatter: (value) => value.toFixed(2),
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
      data: [1, 2, 3, 4, 5],
      name: 'Number of Elevators',
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
      name: 'Latency (s)',
      nameLocation: 'center',
      nameGap: 50,
      axisLabel: {
        fontFamily: 'Roboto',
        fontSize: 16,
      },
    },
  ],
  series: [
    {
      name: 'Mean',
      type: 'bar',
      data: [117.954068641431, 55.29700344923757, 46.57176647707238, 44.015681663871305, 42.75975713609125]
    },
    {
      name: 'Max',
      type: 'bar',
      data: [414.3429391204845, 186.59320912277326, 157.90575060830452, 141.0790516170673, 138.57926610531285]
    },
  ],
});