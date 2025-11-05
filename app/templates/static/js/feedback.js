document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('feedbackForm');
  if(form){
    form.addEventListener('submit', e => {
      e.preventDefault();
      const feedback = new FormData(form);
      console.log('Feedback submitted:', Object.fromEntries(feedback.entries()));
      alert('Feedback submitted (mock).');
    });
  }
});
