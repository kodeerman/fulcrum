describe('Stats Engine', () => {
  it('opens from the sign-in page and supports direct reloads', () => {
    cy.visit('/UserLogin')
    cy.contains('a', 'Stats Engine').click()
    cy.location('pathname').should('eq', '/stats')
    cy.contains('h1', 'Stats Engine').should('be.visible')
    cy.reload()
    cy.contains('h1', 'Stats Engine').should('be.visible')
    cy.go('back')
    cy.location('pathname').should('eq', '/UserLogin')
  })

  it('calculates descriptive statistics using the live Fulcrum API', () => {
    // Observe the real request without replacing the backend response.
    cy.intercept('POST', '/api/stats/describe').as('describeSample')
    cy.visit('/stats')
    cy.get('textarea').type('2, 4, 4, 4{enter}5 5 7 9')
    cy.contains('button', 'Calculate').click()
    cy.wait('@describeSample').its('response.statusCode').should('eq', 200)

    cy.contains('th', /^Mean$/)
      .siblings('td')
      .should('have.text', '5')
    cy.contains('th', /^Median$/)
      .siblings('td')
      .should('have.text', '4.5')
    cy.contains('th', /^Mode$/)
      .siblings('td')
      .should('have.text', '4')
  })

  it('previews a CSV and calculates grouped summaries after import', () => {
    cy.intercept('POST', '/api/stats/describe').as('describeGroups')
    cy.visit('/stats')
    cy.contains('button', 'Upload CSV').click()
    cy.get('#stats-file').selectFile({
      contents: Cypress.Buffer.from('condition,score\nA,2\nA,4\nB,6\nB,8\nB,'),
      fileName: 'scores.csv',
      mimeType: 'text/csv',
    })
    cy.contains('Preview scores.csv').should('be.visible')
    cy.contains('button', 'Calculate').should('not.exist')
    cy.contains('button', 'Import dataset').click()
    cy.get('#stats-group').select('condition')
    cy.contains('1 of 5 rows excluded').should('be.visible')
    cy.contains('button', 'Calculate').click()
    cy.wait('@describeGroups').its('response.statusCode').should('eq', 200)
    cy.contains('th', /^Mean$/)
      .parent()
      .find('td')
      .then(cells => {
        expect([...cells].map(cell => cell.textContent.trim())).to.deep.equal([
          '3',
          '7',
        ])
      })
  })
})
