import React from 'react';
import Plot from 'react-plotly.js';

const ChartRenderer = ({ chartData }) => {
    if (!chartData) return null;

    const { type, title, x_label, y_label, data } = chartData;

    // Convert data to Plotly format
    let plotData = [];
    const labels = data.map(d => d.label);
    const values = data.map(d => d.value ?? d.amount ?? 0);

    if (type === 'bar') {
        plotData = [{
            x: labels,
            y: values,
            type: 'bar',
            marker: { color: '#3b82f6' }
        }];
    } else if (type === 'line') {
        plotData = [{
            x: labels,
            y: values,
            type: 'scatter',
            mode: 'lines+markers',
            line: { color: '#3b82f6' }
        }];
    } else if (type === 'pie') {
        plotData = [{
            labels: labels,
            values: values,
            type: 'pie'
        }];
    }

    const layout = {
        title: title,
        xaxis: { title: x_label, type: 'category' },
        yaxis: { title: y_label },
        autosize: true,
        margin: { l: 50, r: 50, b: 50, t: 50, pad: 4 },
        font: { family: 'Inter, sans-serif' }
    };

    return (
        <div className="w-full h-80 bg-white p-2 rounded-lg shadow-sm border border-gray-100 mb-4">
            <Plot
                data={plotData}
                layout={layout}
                useResizeHandler={true}
                style={{ width: "100%", height: "100%" }}
                config={{ displayModeBar: false }}
            />
        </div>
    );
};

export default ChartRenderer;
