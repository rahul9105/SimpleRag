const fileList = document.querySelector('.file-list');
const fileBrowserButton = document.querySelector('.file-browser-button');
const fileBrowserInput = document.querySelector('.file-browser-input');
const fileUploadBox = document.querySelector('.file-upload-box');
const clearList = document.querySelector('.clear-list span#clear-list');
const deleteFiles = document.querySelector('.clear-list span#delete-files');
const filesCompletedStatus = document.querySelector(".file-completed-status");
const commenceChat = document.querySelector(".commence-chat #commence-chat");
// const chatLoadingProgress = document.getElementById('loading-progress');
// const chatLoadingProgressBar = document.querySelector('.file-progress');
// const allowedFileTypes = [
//     "abw",
//     "bmp",
//     "csv",
//     "cwk",
//     "dif",
//     "doc",
//     "docx",
//     "dot",
//     "eml",
//     "epub",
//     "et",
//     "eth",
//     "heic",
//     "htm",
//     "html",
//     "hwp",
//     "jpeg",
//     "jpg",
//     "md",
//     "mcw",
//     "msg",
//     "mw",
//     "org",
//     "p7s",
//     "pbd",
//     "pdf",
//     "png",
//     "pot",
//     "ppt",
//     "pptm",
//     "pptx",
//     "prn",
//     "rst",
//     "rtf",
//     "sdp",
//     "svg",
//     "sxg",
//     "tiff",
//     "txt",
//     "tsv",
//     "xls",
//     "xlsm",
//     "xlsx",
//     "xml",
//     "zabw"
// ];
const allowedFileTypes = ['txt', 'doc', 'docx', 'pdf', 'pptx']
let askButton;
let userQueryInput;
let chatTextArea;

const socket = io();
let socketId = null;
socket.connect('http://localhost:5000');
socket.on('connect', () => {
    socketId = socket.id;
    console.log('Socket ID:', socketId);
});

function typeWriter(txt, qSelector, i=0) {
    let speed = 10;
    if (i < txt.length) {
        document.querySelectorAll(qSelector)[document.querySelectorAll(qSelector).length-1].innerHTML += txt.charAt(i);
        i++;
        setTimeout(typeWriter, speed, txt, qSelector, i);
    }
    setTimeout(chatTextArea.scrollTop = chatTextArea.scrollHeight, txt.length * speed);
}

const attachAskButtonEventListener = () => {
    askButton.addEventListener('click', (event) => {
        if (userQueryInput.value != "") {
            const userQuery = userQueryInput.value;
            chatTextArea.insertAdjacentHTML('beforeend', userChatTemplate(userQuery));
            typeWriter(userQuery, ".chat-text-area .user-message #message");
            userQueryInput.value = "";
            chatTextArea.scrollTop = chatTextArea.scrollHeight;
            $.ajax({
                type: "POST",
                url: "/simple-rag/ask",
                data: { query: userQuery },
                beforeSend: function () {
                    askButton.innerHTML = `<div class="spinner-border text-light" role="status">
                                                <span class="visually-hidden">Loading...</span>
                                            </div>`;
                },
                success: function (response) {
                    if (response.status == 200) {
                        chatTextArea.insertAdjacentHTML('beforeend', botChatTemplate(response.answer));
                        typeWriter(response.answer, ".chat-text-area .bot-message #message");
                        chatTextArea.scrollTop = chatTextArea.scrollHeight;
                    }
                    else {
                        chatTextArea.insertAdjacentHTML('beforeend', botChatTemplate(response.message));
                        typeWriter(response.message, ".chat-text-area .bot-message #message");
                        chatTextArea.scrollTop = chatTextArea.scrollHeight;
                        Swal.fire({
                            icon: 'error',
                            title: 'Error',
                            text: response.message,
                            showConfirmButton: false,
                            timer: 1500
                        })
                    }
                },
                complete: function () {
                    askButton.innerHTML = `Ask`;
                },
            })
        }
    })
};

const userChatTemplate = (userQuery) => {
    return `<div class="user-message">
                <span id="message"></span>
                <span id="message-icon"><i class="fa-solid fa-user"></i></span>
            </div>`
}

const botChatTemplate = (botResponse) => {
    return `<div class="bot-message">
                <span id="message-icon"><i class="fa-solid fa-robot"></i></span>
                <span id="message"></span>
            </div>`
}

const formatSize = (size) => {
    if (size < 1024) {
        return size + ' B';
    } else if (size < 1048576) {
        return (size / 1024).toFixed(0) + ' KB';
    } else if (size < 1073741824) {
        return (size / 1048576).toFixed(0) + ' MB';
    } else if (size < 1099511627776) {
        return (size / 1073741824).toFixed(0) + ' GB';
    }
}

const handelFilesUploading = (file, index) => {
    var formData = new FormData();
    var request = new XMLHttpRequest();
    request.responseType = 'json';
    var fileName = file.name;
    var fileSize = file.size;
    document.cookie = `filesize=${fileSize}`;
    formData.append('file', file);
    request.upload.addEventListener('progress', (event) => {
        var loaded = event.loaded;
        var total = event.total;
        var percent = (loaded / total) * 100;
        fileList.querySelectorAll('.file-progress')[index].style.width = `${percent}%`;
        fileList.querySelectorAll(`.file-size`)[index].innerText = `${formatSize(loaded)} / ${formatSize(total)}`;
    })

    request.addEventListener('load', (event) => {
        if (request.status == 200) {
            fileList.querySelectorAll('.file-status')[index].innerText = "Uploaded";
            fileList.querySelectorAll('.file-progress')[index].style.width = `100%`;
            fileList.querySelectorAll('.file-size')[index].innerText = `${formatSize(fileSize)} / ${formatSize(fileSize)}`;
            filesCompletedStatus.innerText =  `${parseInt(filesCompletedStatus.innerText.split('/')[0].trim())+1}` + ` / ${filesCompletedStatus.innerText.split('/')[1].trim()}`;
        } else {
            fileList.querySelectorAll('.file-status')[index].innerText = "Error";
        }
        if (parseInt(filesCompletedStatus.innerText.split('/')[0].trim()) == parseInt(filesCompletedStatus.innerText.split('/')[1].split(' ')[1].trim())) {
            commenceChat.classList.add('visible');
        }
    })

    request.addEventListener('error', (event) => {
        fileList.querySelectorAll('.file-status')[index].innerText = "Error";
    });

    request.addEventListener('abort', (event) => {
        fileList.querySelectorAll('.file-status')[index].innerText = "Cancelled";
        fileList.querySelectorAll('.cancel-button')[index].style.color = "#ff0000";
        fileList.querySelectorAll('.file-status')[index].style.color = "#ff0000";
    })

    request.open('POST', '/simple-rag/upload');
    request.send(formData);

    fileList.querySelectorAll('.cancel-button')[index].addEventListener('click', (event) => {
        request.abort();
        fileList.querySelectorAll('.file-status')[index].innerText = "Cancelled";
        fileList.querySelectorAll('.cancel-button')[index].style.color = "#ff0000";
        fileList.querySelectorAll('.file-status')[index].style.color = "#ff0000";
    });
};

const createFileItemHtml = (file, index) => {
    const {name, size} = file;
    const extension = name.split('.').pop();
    return `<li class="file-item">
                    <div class="file-extension">${extension}</div>
                    <div class="file-content-wrapper">
                        <div class="file-content">
                            <div class="file-details">
                                <h5 class="file-name">${name.length > 45 ? name.substr(0, 42)+'...' : name}</h5>
                                <div class="file-info">
                                    <small class="file-size">0 / ${formatSize(size)}</small>
                                    <small class="file-divider">.</small>
                                    <small class="file-status${allowedFileTypes.includes(extension.toLowerCase()) ? '' : ' not-allowed'}">${allowedFileTypes.includes(extension.toLowerCase()) ? 'Uploading...' : 'Not Allowed'}</small>
                                </div>
                            </div>
                            <button class="cancel-button">
                                <i class="bx bx-x"></i>
                            </button>
                        </div>
                        <div class="file-progress-bar">
                            <div class="file-progress"></div>
                        </div>
                    </div>
                </li>`;
};

const handelSelectedFiles = (files) => {
    if (files.length == 0) return;

    document.querySelector(".clear-list").classList.add("visible");
    filesCompletedStatus.innerText = `0 / ${files.length} Files Uploaded`;
    fileUploadBox.classList.add('hidden');
    // commenceChat.classList.add('visible');

    files.forEach((file, index) => {
        const fileItemHtml = createFileItemHtml(file, index);
        const fileExtension = file.name.split('.').pop();
        fileList.insertAdjacentHTML('afterbegin', fileItemHtml);
        if (allowedFileTypes.includes(fileExtension.toLowerCase())) {
            handelFilesUploading(file, index);
        }
    });
}

fileUploadBox.addEventListener('drop', (event) => {
    event.preventDefault();
    handelSelectedFiles([...event.dataTransfer.files]);
    fileUploadBox.classList.remove('active');
    fileUploadBox.querySelector(".file-instruction").innerText = "Drag files here or";
});

fileUploadBox.addEventListener('dragover', (event) => {
    event.preventDefault();
    fileUploadBox.classList.add('active');
    fileUploadBox.querySelector(".file-instruction").innerText = "Release to upload file or";
});

fileUploadBox.addEventListener('dragleave', (event) => {
    event.preventDefault();
    fileUploadBox.classList.remove('active');
    fileUploadBox.querySelector(".file-instruction").innerText = "Drag files here or";
});

clearList.addEventListener('click', (event) => {
    fileList.innerHTML = "";
    // document.querySelector(".clear-list").classList.remove("visible");
    fileUploadBox.classList.remove('hidden');
    fileBrowserInput.value = "";
    fileUploadBox.classList.remove('active');
    fileUploadBox.querySelector(".file-instruction").innerText = "Drag files here or";
    Swal.fire({
        icon: 'success',
        title: 'List Cleared',
        text: "List Cleared Successfully",
        showConfirmButton: false,
        timer: 1500
    })
})

deleteFiles.addEventListener('click', (event) => {
    fileList.innerHTML = "";
    document.querySelector(".clear-list").classList.remove("visible");
    fileUploadBox.classList.remove('hidden');
    fileBrowserInput.value = "";
    fileUploadBox.classList.remove('active');
    fileUploadBox.querySelector(".file-instruction").innerText = "Drag files here or";
    filesCompletedStatus.innerText = `0 / 0 Files Uploaded`;
    commenceChat.classList.remove('visible');
    $.ajax({
        type: "POST",
        url: "/simple-rag/delete-files",
        success: function (response) {
            if (response.status == 200) {
                // Swal.fire({
                //     icon: 'success',
                //     title: 'Files Deleted',
                //     text: response.message,
                //     showConfirmButton: false,
                //     timer: 1500
                // })
                console.log(response.message);
            }
            else {
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: response.message,
                    showConfirmButton: false,
                    timer: 1500
                })
            }
        },
        error: function (response) {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: response.message,
                showConfirmButton: false,
                timer: 1500
            })
        }
    })
})

fileBrowserInput.addEventListener('change', (event) => handelSelectedFiles([...event.target.files]));
fileBrowserButton.addEventListener('click', () => fileBrowserInput.click());

commenceChat.addEventListener('click', (event) => {
    document.querySelector("main").innerHTML = `<div class="loader" style="height:150px; width:150px;"></div>
    <div class="mt-4">
        <span id="loading-text" style="font-size:1.5rem;">Preparing...</span>
        <span class="ms-2" id="loading-progress" style="font-size:1.5rem;">0%</span>
    </div>
    <div class="file-progress-bar my-4 w-75" style="background-color:lightgray !important;">
        <div class="file-progress" style="width: 0%; height: 10px !important; background-color: blue !important;"></div>
    </div>
    <h4>Analysing Uploaded Files...</h4>`;
    let files;
    const chatLoadingProgress = document.getElementById('loading-progress');
    const chatLoadingProgressBar = document.querySelector('.file-progress');
    const loadingText = document.getElementById('loading-text');
    socket.on('progress', (data) => {
        chatLoadingProgressBar.style.width = `${data.progress}%`;
        chatLoadingProgress.innerText = `${data.progress}%`;
        if (!data.message == '') {
            loadingText.innerText = data.message;
        }
    })
    $.ajax({
        type: "POST",
        // url: "/simple-rag/commence-chat",
        url: "/simple-rag/commence-chat/"+socketId,
        success: function (response) {
            if (response.status == 200) {
                document.querySelector("main").innerHTML = response.htmlTemplate;
                files = response.files;
            }
            else {
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: response.message,
                    showConfirmButton: false,
                    timer: 1500
                })
            }
        },
        complete: function () {
            setTimeout(() => {
                askButton = document.querySelector('#ask-button');
                userQueryInput = document.querySelector('#user-input');
                chatTextArea = document.querySelector(".chat-text-area");
                typeWriter("How can I assist you today?", ".chat-text-area .bot-message #message");
                attachAskButtonEventListener();
                chatTextArea.scrollTop = chatTextArea.scrollHeight;
                files.forEach((item) => {
                    let name = item.split('\\')[item.split('\\').length-1];
                    let html = `<li class="file">
                        <span class="extension">${item.split('.')[name.split('.').length-1]}</span>
                        <span class="name">${name.slice(5)}</span>
                    </li>`
                    document.querySelector("ul.uploaded-files").insertAdjacentHTML('afterbegin', html);
                });
            }, 1500);
        },
    })
});