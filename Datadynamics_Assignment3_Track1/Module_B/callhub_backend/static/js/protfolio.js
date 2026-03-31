document.getElementById("portfolioForm").addEventListener("submit", function(e){

e.preventDefault()

let project = document.getElementById("project_name").value
let description = document.getElementById("description").value

fetch("/portfolio", {

method:"POST",

headers:{
"Content-Type":"application/json"
},

body:JSON.stringify({
project:project,
description:description
})

})

.then(res=>res.json())

.then(data=>{

if(data.success){

let list = document.getElementById("portfolioList")

let item = document.createElement("li")

item.innerText = project + " - " + description

list.appendChild(item)

}

})

})