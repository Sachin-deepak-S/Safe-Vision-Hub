// Example Chart.js helper for admin dashboards
document.addEventListener('DOMContentLoaded', () => {
  const ctx = document.getElementById('apiUsageChart');
  if(ctx){
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'],
        datasets:[{
          label:'API Calls',
          data:[12,25,30,22,40,10,18],
          backgroundColor:'#3b82f6', borderColor:'#3b82f6', fill:false
        }]
      },
      options:{responsive:true}
    });
  }
});
