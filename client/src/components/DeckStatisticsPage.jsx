import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import Header from './Header'; // Shared header
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'; // Uncomment
import { Pie } from 'react-chartjs-2'; // Uncomment
import { getDeckStats } from '../api'; // Import the new API function

ChartJS.register(ArcElement, Tooltip, Legend); // Uncomment

// Mock data structure
// const mockStatsData = { ... };

// Uncomment Chart Data generation
// /* // Remove opening comment
const generateChartData = (counts) => {
    const labels = Object.keys(counts);
    const data = Object.values(counts);
    // Filter out categories with 0 count for cleaner chart
    const filteredLabels = labels.filter((_, index) => data[index] > 0);
    const filteredData = data.filter(count => count > 0);
    const backgroundColors = [
        'rgba(54, 162, 235, 0.7)', // New (Blue)
        'rgba(255, 159, 64, 0.7)', // Learning (Orange)
        'rgba(255, 99, 132, 0.7)', // Relearning (Red)
        'rgba(75, 192, 192, 0.7)', // Young (Green)
        'rgba(46, 139, 87, 0.7)', // Mature (Darker Green)
        'rgba(255, 206, 86, 0.7)', // Suspended (Yellow)
        'rgba(108, 117, 125, 0.7)', // Buried (Grey)
    ];
    const borderColors = [
        'rgba(54, 162, 235, 1)',
        'rgba(255, 159, 64, 1)',
        'rgba(255, 99, 132, 1)',
        'rgba(75, 192, 192, 1)',
        'rgba(46, 139, 87, 1)',
        'rgba(255, 206, 86, 1)',
        'rgba(108, 117, 125, 1)',
    ];
    // Filter colors based on labels that have data
    const filteredBackgroundColors = labels.map((label, index) => data[index] > 0 ? backgroundColors[index] : null).filter(color => color !== null);
    const filteredBorderColors = labels.map((label, index) => data[index] > 0 ? borderColors[index] : null).filter(color => color !== null);

    return {
        labels: filteredLabels,
        datasets: [
            {
                label: '# of Cards',
                data: filteredData,
                backgroundColor: filteredBackgroundColors,
                borderColor: filteredBorderColors,
                borderWidth: 1,
            },
        ],
    };
};
// */ // Remove closing comment

function DeckStatisticsPage({ user, onLogout }) {
  const { deckId } = useParams();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [deckName, setDeckName] = useState('Loading Deck Name...');

  useEffect(() => {
    // Fetch deck name (using localStorage for now)
    const storedDeckName = localStorage.getItem('currentDeckName');
    setDeckName(storedDeckName || `Deck ${deckId}`);

    // Fetch stats data (no timeframe needed)
    const fetchStats = async () => {
      setLoading(true);
      setError('');
      setStats(null); 
      try {
         // Call API without timeframe
         const response = await getDeckStats(deckId);
         console.log("Received stats data:", response);
         if (response && response.counts && typeof response.total !== 'undefined') {
            setStats(response);
         } else {
            console.error("Invalid stats data received:", response);
            setError("Received invalid data format from server.");
            setStats(null);
         }
      } catch (err) {
         console.error("Error fetching deck stats:", err);
         setError(err.response?.data?.error || "Failed to load statistics.");
         setStats(null);
         if (err.response?.status === 401) {
            if (typeof onLogout === 'function') onLogout();
         }
      } finally {
         setLoading(false);
      }
    };
    fetchStats();

  }, [deckId, onLogout]); // Remove timeframe dependency

  // Function to calculate percentage
  const calculatePercentage = (count, total) => {
    if (!total || total === 0) return '0.0%'; 
    return ((count / total) * 100).toFixed(1) + '%';
  };

  // Generate chart data
  const chartData = stats ? generateChartData(stats.counts) : null;

  return (
    <div className="container mt-4">
      <Header user={user} onLogout={onLogout} />
      <h2>Statistics for {deckName}</h2>

      {/* Loading/Error Display */}
      {loading && <p>Loading statistics...</p>}
      {error && <div className="alert alert-danger">{error}</div>}

      {/* Statistics Display Area */}
      {!loading && !error && stats && (
        <div className="row">
          {/* Chart */}
          <div className="col-md-6 d-flex justify-content-center align-items-center" style={{ minHeight: '300px' }}>
             {chartData && chartData.labels.length > 0 ? (
                <Pie data={chartData} options={{ maintainAspectRatio: false }} />
             ) : (
                 <p className="text-muted">No card data to display in chart.</p>
             )}
          </div>

          {/* Stats Table/List */}
          <div className="col-md-6">
             <table className="table">
                <thead>
                    <tr>
                        <th>Status</th>
                        <th>Count</th>
                        <th>Percentage</th>
                    </tr>
                </thead>
                <tbody>
                 {stats.counts && Object.entries(stats.counts).map(([status, count]) => (
                    <tr key={status}>
                        <td>{status}</td>
                        <td>{count}</td>
                        <td>{calculatePercentage(count, stats.total)}</td>
                    </tr>
                 ))}
                 {stats.counts && (
                   <tr className="table-group-divider">
                      <td><strong>Total</strong></td>
                      <td><strong>{stats.total}</strong></td>
                      <td><strong>{stats.total > 0 ? '100.0%' : '0.0%'}</strong></td>
                   </tr>
                 )}
                </tbody>
             </table>
             {!stats.counts && <p>No count data found in statistics.</p>} 
          </div>
        </div>
      )}
      {!loading && !error && !stats && <p>No statistics data available.</p>} 
    </div>
  );
}

export default DeckStatisticsPage; 