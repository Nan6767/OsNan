/* FlyArchOs — слайд-шоу во время установки (Calamares). */
import QtQuick 2.0;
import calamares.slideshow 1.0;

Presentation
{
    id: presentation

    function nextSlide() {
        presentation.goToNextSlide();
    }

    Timer {
        id: advanceTimer
        interval: 15000
        running: presentation.activatedInCalamares
        repeat: true
        onTriggered: nextSlide()
    }

    /* --------------------------------------------------- Слайд 1 --- */
    Slide {
        anchors.fill: parent

        Image {
            id: slide1
            source: "slide-1.jpg"
            anchors.top: parent.top
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.margins: 20
            width: parent.width * 0.6
            fillMode: Image.PreserveAspectFit
        }

        Text {
            anchors.top: slide1.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.topMargin: 24
            width: parent.width * 0.82
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            font.pointSize: 16
            color: "#22d3ee"
            text: "Два рабочих окружения в одной системе"
        }

        Text {
            anchors.top: slide1.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.topMargin: 58
            width: parent.width * 0.8
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            font.pointSize: 11
            color: "#c8cbe0"
            text: "Тайлинговый Hyprland для работы с клавиатуры и классическая KDE Plasma — переключаются на экране входа."
        }
    }

    /* --------------------------------------------------- Слайд 2 --- */
    Slide {
        anchors.fill: parent

        Image {
            id: slide2
            source: "slide-2.jpg"
            anchors.top: parent.top
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.margins: 20
            width: parent.width * 0.6
            fillMode: Image.PreserveAspectFit
        }

        Text {
            anchors.top: slide2.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.topMargin: 24
            width: parent.width * 0.82
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            font.pointSize: 16
            color: "#22d3ee"
            text: "Установка полностью офлайн"
        }

        Text {
            anchors.top: slide2.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.topMargin: 58
            width: parent.width * 0.8
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            font.pointSize: 11
            color: "#c8cbe0"
            text: "Все программы уже внутри образа: вы выбираете окружение и наборы ПО, установщик убирает лишнее."
        }
    }

    /* --------------------------------------------------- Слайд 3 --- */
    Slide {
        anchors.fill: parent

        Image {
            id: slide3
            source: "slide-3.jpg"
            anchors.top: parent.top
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.margins: 20
            width: parent.width * 0.6
            fillMode: Image.PreserveAspectFit
        }

        Text {
            anchors.top: slide3.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.topMargin: 24
            width: parent.width * 0.82
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            font.pointSize: 16
            color: "#22d3ee"
            text: "Двенадцать обоев и генератор своих"
        }

        Text {
            anchors.top: slide3.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.topMargin: 58
            width: parent.width * 0.8
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            font.pointSize: 11
            color: "#c8cbe0"
            text: "flyarchos-wallpaper set <название>  ·  случайные обои  ·  flyarchos-wallpaper-gen --list"
        }
    }

    /* Слайд «почти готово» */
    Slide {
        anchors.fill: parent

        Text {
            anchors.centerIn: parent
            width: parent.width * 0.8
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            font.pointSize: 20
            color: "#f0559b"
            text: "Осталось совсем немного…"
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 60
            font.pointSize: 11
            color: "#8a90a6"
            text: "FlyArchOs — Arch Linux, каким он вам нравится"
        }
    }
}
