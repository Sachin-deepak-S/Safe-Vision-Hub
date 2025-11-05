document.addEventListener("DOMContentLoaded", ()=>{
  const btn=document.getElementById("toggleTheme");
  const html=document.documentElement;
  const stored=localStorage.getItem("theme");
  if(stored==="dark"){html.classList.add("dark");}
  if(btn){
    btn.addEventListener("click",()=>{
      html.classList.toggle("dark");
      localStorage.setItem("theme",html.classList.contains("dark")?"dark":"light");
    });
  } else {
    console.warn("toggleTheme button not found on this page");
  }
});
