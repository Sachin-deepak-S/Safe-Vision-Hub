// dashboard.js - for admin interactive dashboard
document.addEventListener('DOMContentLoaded', () => {
  // Toggle dark/light mode button
  const toggleBtn = document.getElementById('toggleTheme');
  if(toggleBtn){
    toggleBtn.addEventListener('click', () => {
      document.documentElement.classList.toggle('dark');
      localStorage.setItem('theme', document.documentElement.classList.contains('dark') ? 'dark' : 'light');
    });

    // load saved theme
    const savedTheme = localStorage.getItem('theme');
    if(savedTheme === 'dark') document.documentElement.classList.add('dark');
    else document.documentElement.classList.remove('dark');
  }

  // Load charts
  const ctxDisagreements = document.getElementById('disagreementChart');
  if(ctxDisagreements){
    new Chart(ctxDisagreements.getContext('2d'), {
      type: 'bar',
      data: {
        labels: ['Mon','Tue','Wed','Thu','Fri'],
        datasets:[{
          label:'Disagreements',
          data:[3,5,2,7,4],
          backgroundColor:'#f87171'
        }]
      },
      options:{responsive:true, plugins:{legend:{display:false}}}
    });
  }

  // Priority feedback mock
  const list = document.getElementById('priorityList');
  if(list){
    const priorityData = [
      {id:'abc123', user:'user1', path:'uploads/file1.jpg'},
      {id:'def456', user:'user2', path:'uploads/file2.mp4'}
    ];
    priorityData.forEach(f => {
      const li = document.createElement('li');
      li.textContent = `${f.id} - ${f.user} - ${f.path}`;
      li.className = "p-2 rounded bg-gray-100 dark:bg-gray-700";
      list.appendChild(li);
    });
  }
});
