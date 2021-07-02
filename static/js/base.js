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