const element = document.getElementById('chart-system-throughput');
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
      data: [20, 19, 18, 17, 16, 15],
      name: 'Mean Time Between Requests (s)',
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
        186.1835094959234 / 186.31329990812952,
        215.82737066987357 / 214.49205722318948,
        304.7135737046539 / 306.52797741267506,
        26585.631230024308 / 12543.125026929107,
        93040.87735298941 / 45249.710744333715,
        160528.16941428368 / 79523.81772432546,
      ],
    },
  ]
});