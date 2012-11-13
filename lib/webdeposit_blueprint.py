# -*- coding: utf-8 -*-
# #
# # This file is part of Invenio.
# # Copyright (C) 2012 CERN.
# #
# # Invenio is free software; you can redistribute it and/or
# # modify it under the terms of the GNU General Public License as
# # published by the Free Software Foundation; either version 2 of the
# # License, or (at your option) any later version.
# #
# # Invenio is distributed in the hope that it will be useful, but
# # WITHOUT ANY WARRANTY; without even the implied warranty of
# # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# # General Public License for more details.
# #
# # You should have received a copy of the GNU General Public License
# # along with Invenio; if not, write to the Free Software Foundation, Inc.,
# # 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""WebDeposit Flask Blueprint"""
import os
import shutil
import json
#from werkzeug import *
from glob import iglob
from flask import render_template, \
                  request, \
                  jsonify, \
                  redirect, \
                  url_for, \
                  send_from_directory

from invenio.webinterface_handler_flask_utils import _, InvenioBlueprint

from invenio.sherpa_romeo import SherpaRomeoSearch
from invenio.webdeposit_utils import create_doc_type, \
                                     get_current_form, \
                                     draft_field_set, \
                                     draft_field_list_add, \
                                     delete_draft, \
                                     draft_field_get_all, \
                                     pretty_date

from webdeposit_load_forms import forms

globals().update(forms)


# from invenio.webuser_flask import current_user

blueprint = InvenioBlueprint('websubmit', __name__,
                              url_prefix="/submit",
                              config='invenio.websubmit_config',
                              #breadcrumbs=[(_('Comments'),
                              #              'webcomment.subscribtions')],
                              menubuilder=[('main.websubmit',
                                          _('Submit'),
                                            'websubmit.add', 2)],
                              breadcrumbs=[(_('Submit'), 'submit'),
                                          (_('Add an Article'), \
                                            'websubmit.add')])


@blueprint.route('/websubmit/submitted', methods=['GET', 'POST'])
def submit():
    if request.method == 'POST':
        doctitle = request.form['doctitle']
        author = request.form['author']
        abstract = request.form['abstract']
        pagesnum = request.form['pagesnum']
        language = request.form['language']
        date = request.form['date']
        keywords = request.form['keywords']
        keywords2 = request.form['keywords2']
        notes = request.form['notes']
        uploaded_file = request.files['file']
        filename = secure_filename(uploaded_file.filename)
        uploaded_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        send_from_directory(app.config['UPLOAD_FOLDER'], filename)
        return render_template('websubmit_submitted.html', \
                                doctitle=doctitle, author=author , abstract=abstract , \
                                pagesnum=pagesnum , language=language , date=date , \
                                keywords=keywords, keywords2=keywords2, notes=notes , validated=True)
    else:
        return render_template('websubmit_submitted.html', validated=False)


@blueprint.route('/websubmit/<doc_type>/_upload', methods=['POST', 'GET'])
def plupload():
    if request.method == 'POST':
        try:
            chunks = request.form['chunks']
            chunk = request.form['chunk']
        except KeyError:
            chunks = None
            pass
        name = request.form['name']

        upload_folder = '/opt/invenio/var/tmp/webdeposit_uploads'
        current_chunk = request.files['file']

        try:
            filename = name + "_" + chunk
        except Exception:
            filename = name
        current_chunk.save(os.path.join(upload_folder, filename))

        from invenio.webuser_flask import current_user
        draft_id = get_current_form(current_user.get_id())[0]

        if chunks is None: #file is a single chunk
            file_path = os.path.join(upload_folder, name)

            draft_field_list_add(current_user.get_id(), \
                                 draft_id, \
                                 "files", \
                                 file_path)
        elif int(chunk) == int(chunks) - 1:
            '''All chunks have been uploaded!
                start merging the chunks'''

            chunk_files = []
            for filename in iglob(os.path.join(upload_folder, name + '_*')):
                chunk_files.append(filename)

            #Sort files in numerical order
            chunk_files.sort(key=lambda x: int(x.split("_")[-1]))

            file_path = os.path.join(upload_folder, name)
            destination = open(file_path, 'wb')
            for filename in chunk_files:
                shutil.copyfileobj(open(filename, 'rb'), destination)
            destination.close()

            draft_field_list_add(current_user.get_id(), \
                                 draft_id, \
                                 "files", \
                                 file_path)
    return ""


@blueprint.route('/websubmit/<doc_type>/_autocomplete/<uuid>', \
                 methods=['GET', 'POST'])
def autocomplete(doc_type, uuid):
    from invenio.webuser_flask import current_user

    query = request.args.get('term')
    field_type = request.args.get('type')

    form = get_current_form(current_user.get_id(), uuid=uuid)[1]
    form.__dict__["_fields"][field_type].process_data(query)

    #Check if field has an autocomplete function
    if hasattr(form.__dict__["_fields"][field_type], "autocomplete"):
        return json.dumps(form.__dict__["_fields"][field_type].autocomplete())
    else:
        return []


@blueprint.route('/websubmit/<doc_type>/_ISSN/<uuid>', methods=['GET', 'POST'])
# @cache.cached(timeout=50, key_prefix='issn')
def autocomplete_ISSN_Conditions(doc_type, uuid):
    from invenio.webuser_flask import current_user
    query = request.args.get('title')

    s = SherpaRomeoSearch()

    s.search_journal(query)

    response = dict()
    response['issn'] = s.parser.get_issn()
    response['conditions'] = s.parser.get_conditions()

    draft_id, form = get_current_form(current_user.get_id(), uuid=uuid)

    draft_field_set(current_user.get_id(), \
                    draft_id, \
                    "issn", \
                    response['issn'])
    draft_field_set(current_user.get_id(), \
                    draft_id, \
                    "conditions", \
                    response['conditions'])

    return json.dumps(response)


@blueprint.route('/websubmit/<doc_type>/_errorCheck/<uuid>')
def error_check(doc_type, uuid):
    val = request.args.get('attribute')
    name = request.args.get('name')

    from invenio.webuser_flask import current_user


    # draft_id, form = get_current_form(user_id)
    # form_type = form.__class__.__name__

    draft_field_set(current_user.get_id(), uuid, str(name), str(val))
    draft_id, form = get_current_form(current_user.get_id(), uuid=uuid)


    if name == "issn" or name == "journal":
        draft_field_set(current_user.get_id(), draft_id, "conditions", None)


    form.__dict__["_fields"][name].process_data(val)

    try:
        json_response = jsonify(form.__dict__["_fields"][name].pre_validate())
    except TypeError:
        json_response = jsonify({"error_message": "", "error": 0})
    return json_response


@blueprint.route('/<doc_type>/websubmit_delete/<uuid>')
def delete(doc_type, uuid=None):
    from invenio.webuser_flask import current_user

    latest_draft_id = delete_draft(current_user.get_id(), doc_type, uuid)

    return redirect(url_for("websubmit.add", \
                            doc_type=doc_type, \
                            uuid=latest_draft_id))


@blueprint.route('/<doc_type>/new/')
def create_new(doc_type):
    from invenio.webuser_flask import current_user

    draft_id = create_doc_type(current_user.get_id(), doc_type)[0]
    return redirect(url_for("websubmit.add", doc_type=doc_type, uuid=draft_id))


@blueprint.route('/websubmit')
@blueprint.route('/websubmit/')
@blueprint.route('/websubmit/<doc_type>')
@blueprint.route('/websubmit/<doc_type>/<uuid>')
def add(doc_type=None, uuid=None):
    from invenio.webuser_flask import current_user

    if doc_type is None:
        return render_doc_types()
    elif uuid is not None:
        #draft_id is the same
        #it returns a new one if it doesn't exist
        draft_id, form = get_current_form(current_user.get_id(), uuid=uuid)
    else:
        draft_id, form = get_current_form(current_user.get_id(), doc_type)
        return redirect(url_for("websubmit.add", \
                                doc_type=doc_type, \
                                uuid=draft_id))

    drafts = draft_field_get_all(current_user.get_id(), \
                                 doc_type, \
                                 "title")
    drafts = sorted(drafts, key=lambda draft: draft['timestamp'], reverse=True)
    for draft in drafts:
        draft['timestamp'] = pretty_date(draft['timestamp'])
    return render_template('websubmit_add.html', \
                           doc_type=doc_type,
                           form=form, \
                           drafts=drafts, \
                           draft_id=draft_id)

    """
    form = ArticleForm()
    form_type = form.__class__.__name__

    if current_user.get_id() == 0:
        form._drafting = False
    if not form._drafting: #if guest user or drafting is not enabled
        return render_template('websubmit_add.html', form=form, drafts=[])

    if draft_id is None: #get the latest draft

        draft_id = get_current_draft(current_user.get_id()).draft_id

        if draft_id is None:
            draft_id = new_draft(current_user.get_id(), form_type)
            return redirect(url_for("websubmit.add", draft_id=draft_id))

        draft = get_draft(current_user.get_id(), draft_id, form_type)

    elif draft_id == 0:
        draft_id = new_draft(current_user.get_id(), form_type)
        return redirect(url_for("websubmit.add", draft_id=draft_id))
        draft = get_draft(current_user.get_id(), str(draft_id))
    else:
        draft = get_draft(current_user.get_id(), draft_id, form_type)
        if draft is None:
            draft_id = new_draft(current_user.get_id())
            return redirect(url_for("websubmit.add", draft_id=draft_id))

    set_current_draft(current_user.get_id(), draft_id)

    for fieldName, fieldData in form.data.iteritems():
        if fieldName in draft:
            form[fieldName].process_data(draft[fieldName])

    conditions = draft_field_get(current_user.get_id(), draft_id, form_type, "conditions")
    drafts = draft_field_get_all(current_user.get_id(), form_type, "title")
    if not isinstance(conditions, str) and conditions is not None :
        conds = []
        for condition in conditions:
            conds.append(escape(condition))
        conditions = conds
        return render_template('websubmit_add.html', \
                               form=form, \
                               conditions=conditions, \
                               drafts=drafts, \
                               draft_id=draft_id)
    elif conditions is not None:
        conditions = [escape(conditions)]
        return render_template('websubmit_add.html', \
                               form=form, \
                               conditions=conditions, \
                               drafts=drafts, \
                               draft_id=draft_id)
    else:
        return render_template('websubmit_add.html', \
                               form=form, \
                               drafts=drafts, \
                               draft_id=draft_id)
    """


def render_doc_types():
    """
    Renders the doc types(workflows) list
    """
    from webdeposit_load_doc_types import doc_types

    return render_template('websubmit_doc_types.html', \
                           docs=doc_types)
