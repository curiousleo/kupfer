====================
GTK+ Theming Support
====================

----------------------------
Changing Kupfer's Appearance
----------------------------

.. contents::


Introduction
============

In Kupfer's new 2011 interface, the interface elements are marked-up so
that they can be changed using GTK+'s normal styling mechanism.

For the general topic of GTK+ themes, read `this excellent tutorial.`__

__ http://live.gnome.org/GnomeArt/Tutorials/GtkThemes


Kupfer's UI can be themed by using the normal GtkRc style language.
Theming can change colors and some pre-defined parameters, but
not the layout.

Example Style
=============

The following example style includes inline comments::

    style "dark"
    {
            ## bg: background color
            bg[NORMAL] = "#333"
            bg[SELECTED] = "#000"
            bg[ACTIVE] = "#222"
            bg[PRELIGHT] = "#222"
            bg[INSENSITIVE] = "#333"

            ## fg: foreground text color
            fg[NORMAL] = "#DDD"
            fg[SELECTED] = "#EEE"
            fg[ACTIVE] = "#EEE"
            fg[PRELIGHT] = "#EEE"
            fg[INSENSITIVE] = "#DDD"

            ## text: text color in input widget and treeview
            text[NORMAL] = "#EEE"
            text[SELECTED] = "#EEE"
            text[ACTIVE] = "#EEE"
            text[PRELIGHT] = "#EEE"
            text[INSENSITIVE] = "#EEE"

            ## base: background color in input widget and treeview
            base[NORMAL] = "#777"
            base[SELECTED] = "#100"
            base[ACTIVE] = "#112"
            base[PRELIGHT] = "#777"
            base[INSENSITIVE] = "#777"

        ## These are UI Widget style properties with their approximate
        ## default values. These can all be overidden in the theme.

        ## The MatchView is the bezel around each pane in the interface

        MatchView :: corner-radius = 15
        MatchView :: opacity = 95

        ## The Search controls the result list

        Search :: list-opacity = 93
        Search :: list-length = 200

        ## The KupferWindow is the whole main window
        KupferWindow :: corner-radius = 15
        KupferWindow :: opacity = 85
        KupferWindow :: decorated = 0
        KupferWindow :: border-width = 8

    }

    ## These are the two defined icon sizes
    gtk-icon-sizes="kupfer-small=24,24:kupfer-large=128,128"

To apply this style, it must be matched against the widgets in the UI
using their names, as follows::

    ## The main window is 'kupfer'
    widget "kupfer" style "dark"
    widget "kupfer.*" style "dark"

    ## The window with result list is 'kupfer-list'
    widget "kupfer-list.*" style "dark"

    ## Additional less used items:
    ## The menu button is '*.kupfer-menu-button'
    ## The description text is '*.kupfer-description'
    ## The context menu is '*.kupfer-menu'


Injecting a Custom Style
========================

Any user can override the GTK+ style used for their applications. But
more conventient is injecting the gtkrc at runtime by means of a Kupfer
plugin. See ``kupfer/plugin/customtheme.py`` for an example.


Icons
=====

The kupfer-specific icon names we use are:

+ ``kupfer``  (application)
+ ``kupfer-catalog``  (root catalog)
+ ``kupfer-execute`` (default action icon)
+ ``kupfer-launch``  (default launch icon)
+ ``kupfer-object``  (blue box generic object icon)
+ ``kupfer-object-multiple`` (multiple generic objects)

.. vim: ft=rst tw=72 et sts=4 sw=4
.. this document best viewed with rst2html
