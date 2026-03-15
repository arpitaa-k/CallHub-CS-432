document.getElementById("loginForm").addEventListener("submit", function(e){

e.preventDefault()

let username = document.getElementById("username").value
let password = document.getElementById("password").value

fetch("/login", {

method:"POST",

headers:{
"Content-Type":"application/json"
},

body:JSON.stringify({
username:username,
password:password
})

})

.then(res=>res.json())

.then(data=>{

if(data.success){

window.location.href="/dashboard"

}

else{

alert("Invalid login")

}

})

})