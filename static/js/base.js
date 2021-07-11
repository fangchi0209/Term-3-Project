checkProcess()

let rateArr = []
let ratingLen = 0
for (let i = 0; i < 5;) {
    i += 0.5
    ratingLen += 10
    let rateDic = {
        ratingNum: i,
        ratingLen: ratingLen + "%"
    }
    rateArr.push(rateDic)
}




async function checkProcess() {
    await fetch("/api/user", { method: "GET" })
        .then(response => {
            return response.json()
        }).then(res => {
            if (res.data == true) {
                signinIcon.style.display = "none"
                signoutIcon.style.display = "block"
            } else {
                signinIcon.style.display = "block"
                signoutIcon.style.display = "none"
            }
        })
}

document.getElementById("signoutProcess").addEventListener("click", logoutProcess)

async function logoutProcess() {
    await fetch("/api/user", {
        method: "DELETE",
        headers: {
            "content-type": "application/json"
        },
    }).then(response => {
        return response.json()
    }).then(result => {
        if (result.ok == true) {
            location.reload()
        }
    })
}