const element = document.getElementById('chart-floor-latency-mean-max');
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
      data: [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
      name: 'Floor',
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
      data: [38.70291918383377, 40.68860665516036, 42.65609258123861, 44.76554586575107, 46.471043307795675, 48.44538091897792, 50.26455864726403, 53.00678411862765, 54.41530391970092, 56.719102754388146, 58.70396701055558, 61.101082047403814, 63.86222393886232, 66.62162959382948, 68.47235843364575, 71.62452590066998, 74.07766553082584]
    },
    {
      name: 'Max',
      type: 'bar',
      data: [133.37152319849702, 149.5396094409516, 149.52741525904275, 159.82521815155633, 148.14974494627677, 141.87939180643298, 138.72756127710454, 174.47362796554808, 157.35112143610604, 168.0848355323542, 145.21891872095875, 156.69267152022803, 178.90530922776088, 180.5266194837168, 176.50148904777598, 186.59320912277326, 183.14009668445215]
    },
  ],
});