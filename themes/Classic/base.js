window.addEventListener("load", function() {
	var options = document.getElementsByClassName("option");
	for(var i = 0; i < options.length; i++) {
		options[i].addEventListener("click", function() {
			if(this.childNodes.length < 2) {
				if(this.className.split(/\s/g).indexOf("correct") != -1) {
					this.innerHTML += "<div class=\"response-wrapper\"><div class=\"response correct\">Correct</div></div>";
				}
				else {
					this.innerHTML += "<div class=\"response-wrapper\"><div class=\"response incorrect\">Incorrect</div></div>";
				}
				this.childNodes[1].style.maxHeight = this.childNodes[1].scrollHeight;
			}
		});
	}
});