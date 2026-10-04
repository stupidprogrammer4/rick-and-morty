(async () => {
    const data = JSON.parse(document.getElementById('chart-data').textContent);
    const style = data.style;
    const money = value => new Intl.NumberFormat('en-US', {maximumFractionDigits: data.decimals}).format(value);
    const stamp = value => !Number.isFinite(value) ? '' : new Intl.DateTimeFormat('en-GB', {timeZone: data.timezone, month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false}).format(new Date(value));
    const box = document.getElementById('ohlc');
    const chart = LightweightCharts.createChart(box, {
        width:box.clientWidth, height:box.clientHeight,
        layout:{background:{type:'solid', color:style.panel_background || style.background}, textColor:style.foreground, fontFamily:'Vazirmatn', fontSize:11},
        grid:{vertLines:{color:style.foreground+'0c'}, horzLines:{color:style.foreground+'12'}},
        rightPriceScale:{borderVisible:false, scaleMargins:{top:.15,bottom:.15}},
        timeScale:{borderVisible:false, timeVisible:true, secondsVisible:false, tickMarkFormatter:time=>stamp(time*1000)},
        localization:{priceFormatter:money, timeFormatter:time=>stamp(time*1000)},
        handleScroll:false, handleScale:false,
    });
    const series = chart.addSeries(LightweightCharts.CandlestickSeries, {
        upColor:style.rising,downColor:style.falling,borderVisible:false,
        wickUpColor:style.rising,wickDownColor:style.falling,
        priceLineVisible:false,lastValueVisible:false,
        priceFormat:{type:'price',precision:data.decimals,minMove:10**(-data.decimals)},
    });
    series.setData(data.candles);
    if (data.latest !== null) {
        series.createPriceLine({price:data.latest,color:style.rising,lineWidth:1,lineStyle:LightweightCharts.LineStyle.Dotted,axisLabelVisible:true});
    }
    chart.timeScale().fitContent();
    const lineBox = document.getElementById('line');
    const line = new ApexCharts(lineBox, {
        chart:{type:'area',width:'100%',height:lineBox.clientHeight,fontFamily:'Vazirmatn',foreColor:style.foreground,background:style.panel_background || style.background,animations:{enabled:false},toolbar:{show:false},zoom:{enabled:false},parentHeightOffset:0},
        series:[{name:style.line_label,data:data.line}],
        colors:[style.rising],stroke:{width:2.5,curve:'straight'},
        fill:{type:'gradient',gradient:{shade:'dark',opacityFrom:.24,opacityTo:.02,stops:[0,100]}},
        dataLabels:{enabled:false},markers:{size:data.candles.length<4?4:0},
        grid:{borderColor:style.foreground+'12',strokeDashArray:3,padding:{top:0,right:8,bottom:0,left:32}},
        xaxis:{type:'datetime',labels:{datetimeUTC:false,formatter:(_value,timestamp)=>stamp(timestamp),style:{fontSize:'10px'}},axisBorder:{show:false},axisTicks:{show:false},tooltip:{enabled:false}},
        yaxis:{opposite:true,forceNiceScale:false,labels:{formatter:money,style:{fontSize:'11px'}}},
        tooltip:{enabled:false},legend:{show:false},
        noData:{text:style.empty_label},
    });
    await line.render();
    if (!data.candles.length) {
        document.getElementById('empty-ohlc').style.display='flex';
    }
    await document.fonts.ready;
    await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    window.chartReady=true;
})();
